#! /usr/bin/env python3

import argparse
import importLib
import json
import os
import sys

from common import *
get_vendor_import_path()

# helpers are vendor specific.
import helpers

# Globals
signal_raised = False
sigterm_raised = False

# NOTE:
# All APIs that talk to server are via ZMQ
# ZMQ is not thread friendly.
# Hence all transactions have to happen via single thread
# Common transactions
#   Read Action request
#   Write Action response
#
# Action request -- Source from Server/Engine
# Action response -- source from any plugin running request method.
#   Plugins runs their request method as *blocking* in individual threads.
#   Hence response can source from any of the multiple threads.
#
# Requirement: Need to react instantaneously for any data from any source.
#
# Current solution:
#   Every plugin is provided an end of a pipem where other end is with main thred.
#   Main thread has list of pipe fds as one per plugin.
#
#   Every time a plugin's threads return from request, it writes something into
#   its end, just to alert the main thread.
#
#   Main thread calls zmq_poll internally  with all fds maintained in main thread
#   Zmq_poll returns for data in ZMQ (from server) or in any of the fds (plugins)
#   Hence handled instantaneously.
#
# Fallback:
#   For any trouble with above, fall back to signal.
#   Plugins when call return from request, raise SIGUSR1 to main thread.
#   This will interrupt zmq_recv which will return with EINTR
#   Generally, prefer not using signals. Hence keep it as fallback.
#

vendor = vendorType.UNKNOWN


# Register signal in global variable
# Anything but SIGTERM is used for re-reading config
# The handler is only registered for SIGHUP & SIGTERM
#
signal_handler(signum, frame):
    global signal_raised, sigterm_raised
    signal_raised = True
    if signum == signal.SIGTERM
        sigterm_raised = True


class LoMPluginHolderFailure(Exception):
    """
    Exception raised for errors in LoMPluginHolder.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message="Unknown error"):
        self.message = "LoMPluginHolderFailure: (" + message + ")"
        super().__init__(self.message)


# Handles a plugin.
# A plugin is per action.
# Mostly managed by main thread.
# Asynchronous request alone is handled in a dedicated thread.
# Hence each instance of a class may have a thread running if request is called
# and yet to complete.
# The request-thread indicates its completion via pipe fd.
# Main thread createa a pipe per LoM instance.
# Main thread listens/read on read-end of pipe, the request thread writes
# when attached plugins return from request call and this thread exits.
# Hence when main thread receives signal via pipe, the request thread will not 
# be alive.
#
class LoMPluginHolder:

    def __init__(self, name:str, plugin_file:str, config: {}):
       
        module_name = ".".join(plugin_file.split(".")[0:-1])
       
        self.plugin = None      # Loaded plugin object
        self.fdR = None         # Pipe read-end to receive signal from request called thread
        self.fdW = None         # Pipe write-end written by req thread when plugin
                                # returns from request call.
        self.thr = None         # Thread object. Exists only when a req is outstanding
                                # until the main thread receives signal from the thread
                                # Main thread call join and reset to None
        self.response = None    # Response returned by plugin for the request
                                # Arrives via the req thread.
        self.request = {}       # Last request sent to plugin
        self.name = ""          # Name of the action handled by this plugin

        try:
            module = importlib.import_module(module_name)
            plugin = getattr(module, "LoMPlugin")(config, do_touch_hearbeat)
            if name != plugin.getName():
                log_error("Action name mismatch in plugin_procs_actions.conf.json")
                return

            if not plugin.is_valid():
                log_error("Failed to init plugin {}".format(plugin))
                return

            ret = register_plugin(name)
            if not ret:
                log_error("Failed to register action {} plugin:{}".format(
                    name, plugin_file))
                return

            self.name = name
            self.plugin = plugin
            log_info("Loaded plugin {} from {}".format(name, plugin_file))

        except Exception as e:
            log_error("Failed to create plugin {}".format(plugin_file))

        return

    def __del__():
        self.plugin = None


    def is_valid(self):
        # If valid, the plugin object exists
        # Thread neutral -- Anyone may call
        #
        if not self.plugin:
            return False

        if self.plugin_timeout:
            log_error("{}:request has and still timed out".format(self.name))
            return False

        return True


    def do_touch_hearbeat(self, instance_id:str):
        # Call back from loaded plugin.
        # It is passed as callable to plugin.
        # It is expected to call periodically when it is blocking
        # on request call.
        # 
        # Hence called from request thread.
        #
        touch_heartbeat(self.name, instance_id)


    def set_pipe(self, fdR:int, fdW:int):
        # Called by main thread as part of initializing this instance
        # for future signalling, when request will be called on plugin.
        #
        # This is called only from main thread.
        #
        if self.fdW != None:
            raise LoMPluginHolderFailure("Internal: Duplicate set_pipe")

        self.fdW = fdW      # Write end of os.pipe
        self.fdR = fdR      # Read  end of os.pipe
        return


    def _raise_signal(self):
        # Called from request thread upon plugin returning from request
        # call to indicate to main thread.
        #
        os.write(self.fdW, b"Hello")
        return


    def _run_request(self):
        # Starting method of the request thread.
        # Running in a dedicated thread. So make a blocking call.
        #
        self.response = self.plugin.request(self.request)

        _raise_signal()     # Inform the completion

        log_info("{}: Completed request".format(self.name))

        # request thread terminates upon return.
        return


    def handle_response(self):
        # Called from main thread, upon receiving signal
        #
        if not chk_thread_done():
            log_error("{}: Internal error: thread is not done in handle_response".format(
                self.name))
            return

        # Write response to backend server/engine.
        #
        write_action_response(self.response)


    def chk_thread_done(self) -> bool:
        # Called from main thread to check on req thread if
        # completed or not.
        # Return false if running
        # Else thread is joined, cleared and any signal written
        # is cleared
        #
        if self.thr:
            if self.thr.is_alive():
                # Request thread has not completed yet.
                if self.plugin_timeout:
                    log_error("{}:request has and still timed out".format(self.name))
                return False

            # Join to formally close
            #
            self.thr.join(0)
            self.thr = None

        self.plugin_timeout = False

        # reset the signal, if any
        # Check before making blocking read, as it might have
        # already got cleared. Read w/o data will block.
        #
        r, _, _ = select.select([fdR], [], [], 0)
        if fdR in r:
            os.read(fdR, 100)

        return True


    def request(self, req:ActionRequest):
        # Called by main thread upon receiving request call to 
        # this plugin from the backend engine / server.
        #
        if not chk_thread_done():
            log_error("{}: request dropped as busy with previous".format(self.name))
            return

        # Kick off thread to raise request to loaded plugin as blocking.
        #
        self.response = {}
        self.thr = threading.Thread(target=self._run_request)
        self.thr.start()

        log_info("{}: request submitted".format(self.name))

        if self.request.timeout > 0:
            # Timed request;
            # Engine waits on timed request, hence no new request is expected.
            # Hence block until timeout or response, whichever earlier.
            #
            r, _, _ = select.select([fdR], [], [], self.request.timeout)
            if fdR in r:
                handle_response()
            else:
                self.plugin_timeout = True
                log_error("{}:request has and still timed out".format(self.name))
        return




def handle_server_request(active_plugin_holders: {}):
    ret, req = read_action_request()
    action_name = req.action_name
    if not ret:
        log_error("Failed to read server request upon poll") 
        return
    if action_name not in active_plugin_holders:
        log_error("requested action {} is not loaded".format(action_name))
        return

    plugin_holder = active_plugin_holders[action_name]
    if not plugin_holder.is_valid():
        log_error("{} is not in valid state to accept request".format(action_name))
        return

    plugin_holder.request(req)
    return


def handle_plugin_holder(plugin_holder: LoMPluginHolder):
    plugin_holder->handle_response()
    return


def main_run(proc_name: str):

    pipe_list = {}
    active_plugin_holders = {}

    while not is_running_config_available():
        # Loop until we get the conf
        log_error("{}: Failing to get plugins for this proc".format(proc_name))
        time.sleep(10)


    plugins = get_proc_plugins_conf("python", proc_name)
    actions_conf = get_actions_conf()

    if not register_client(proc_name):
        log_error("Failing to register client {} with server".format(proc_name))
        return

    try:
        for name, path in plugins.items():
            conf = actions_conf.get(name, {})
            disabled = conf.get("disable", True)
            if not disabled:
                pluginHolder = LoMPluginHolder(name, path, conf)
                if pluginHolder.isValid():
                    fdR, fdW = os.pipe()
                    pluginHolder.set_pipe(fdR, fdW)
                else:
                    log_error("Failed to register plugin {} from {}".format(
                        name, path))

                active_plugin_holders[name] = pluginHolder
                pipe_list[fdR] = name
            else:
                log_error("Skipped disabled plugin {}".format(name)) 
    except Exception as e:
        log_error("{}: plugin failure: exception:{}".format(proc_name, str(e)))

    while not signal_raised:
        # 
        ret = poll_for_data(list(pipe_list.keys()), POLL_TIMEOUT)

        if ret == -1:
            handle_server_request(active_plugin_holders)
        elif ret >= 0:
            if not ret in pipe_list:
                log_error("INTERNAL ERROR: fd {} not in pipe list".format(ret))
            else:
                handle_plugin_holder(pipe_list[ret])
    # SIGHUP will cause a reload of everything.
    deregister_client(proc_name)
    return



def main():
    parser=argparse.ArgumentParser(description="Args for Plugin process for Python plugins")
    parser.add_argument("-p", "--proc-name", required=True, 
            help="Name of this process. The config maps the plugins")
    args = parser.parse_args()

    proc_name = args.proc_name

    syslog_init(proc_name)

    if not c_lib_init(CLIB_DLL_FILE):
        log_error("Failed to init CLIB from {}".format(CLIB_DLL_FILE))
        return

    signal.signal(signal.SIGHUP, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


    while not sigterm_raised:
        main_run(proc_name)


if __name__ == "__main__":
    main()


