#! /usr/bin/env python3

import argparse
import importlib
import json
import os
import select
import signal
import sys
import threading
import time

import clib_bind

from common import *
import gvars

_CT_DIR = os.path.dirname(os.path.abspath(__file__))

# helpers are vendor specific.
# TODO get vendor specific helpers for publish
# Likely ln -s ...helpers.py <vendor file>
# import helpers

# Globals
signal_raised = False
sigusr1_raised = False
sigterm_raised = False
shutdown_request = False

this_proc_name = ""

# Poll to exit for general check, including signals
#
POLL_TIMEOUT = 2

# heartbeat touches from plugins running requests
ACTIVE_POLL_TIMEOUT = 1

# NOTE:
# The APIs that talk to server are not thread friendly (may likely
# use ZMQ). 
# Hence all transactions with server have to happen via single thread
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

# Register signal in global variable
# Anything but SIGTERM is used for re-reading config
# The handler is only registered for SIGHUP & SIGTERM
#
def signal_handler(signum, frame):
    global signal_raised, sigterm_raised, sigusr1_raised

    log_info("signal_handler({}) called".format(signum))
    signal_raised = True
    if signum == signal.SIGUSR1:
        sigusr1_raised = True
    elif signum == signal.SIGTERM:
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
# Request thread periodically call heartbeat touch 
# Main thread scan for touch and send the same to server.
#
#
class LoMPluginHolder:

    def __init__(self, name:str, plugin_file:str, config: {}):
       
        if plugin_file.endswith(".py"):
            module_name = os.path.basename(plugin_file[0:-3])
        else:
            module_name = os.path.basename(plugin_file)


        self.plugin = None      # Loaded plugin object
        self.fdR = None         # Pipe read-end to receive signal from request called thread
        self.fdW = None         # Pipe write-end written by req thread when plugin
                                # returns from request call.
        self.thr = None         # Thread object. Exists only when a req is outstanding
                                # until the main thread receives signal from the thread
                                # Main thread call join and reset to None
                                # Response returned by plugin for the request
        self.response:ActionResponse = None
                                # Arrives via the req thread.
        self.last_request = {}  # Last request sent to plugin
        self.req_start = 0      # Timestamp of request start.
        self.req_end = 0        # Timestamp of request end.
        self.name = ""          # Name of the action handled by this plugin
        self.touch = None       # Last touch from plugin while running request
        self.touchSent = None   # Last touch that is sent
                                # touch stores epoch seconds
        self.action_pause = config.get(gvars.REQ_PAUSE, None)

        try:
            module = importlib.import_module(module_name)
            plugin = getattr(module, "LoMPlugin")(config, self.do_touch_heartbeat)
            if name != plugin.getName():
                log_error("Action name mismatch in plugin_procs_actions.conf.json")
                return

            if not plugin.is_valid():
                log_error("Failed to init plugin {}".format(plugin))
                return

            ret = clib_bind.register_action(name)
            if not ret:
                log_error("Failed to register action {} plugin:{}".format(
                    name, plugin_file))
                return

            self.name = name
            self.plugin = plugin
            log_info("Loaded plugin {} from {}".format(name, plugin_file))

        except Exception as e:
            log_error("Failed to create plugin {} e={}".format(plugin_file, str(e)))

        return

    def __del__(self):
        self.plugin = None
        return


    def is_valid(self):
        # If valid, the plugin object exists
        # Thread neutral -- Anyone may call
        #
        return self.plugin


    def do_touch_heartbeat(self, instance_id:str):
        # Call back from loaded plugin.
        # It is passed as callable to plugin.
        # It is expected to call periodically when it is blocking
        # on request call.
        # 
        # Hence called from request thread.
        #
        self.touch = int(time.time())
        self.instance_id = instance_id
        self._raise_signal()


    def send_heartbeat(self) -> bool:
        if self.touchSent != self.touch:
            self.touchSent = self.touch
            clib_bind.touch_heartbeat(self.name, self.instance_id)
            log_info("plugin_proc:{} plugin:{} Sent heartbeat".
                    format(this_proc_name, self.name))
    

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
        # Called from request thread upon plugin returning from request or heartbeat
        # call to indicate to main thread.
        #
        os.write(self.fdW, b"Hello")
        return


    def _drain_signal(self):
        # reset the signal, if any
        # Check before making blocking read, as it might have
        # already got cleared. Read w/o data will block.
        #
        r, _, _ = select.select([self.fdR], [], [], 0)
        if self.fdR in r:
            os.read(self.fdR, 100)


    def _run_request(self):
        # Starting method of the request thread.
        # Running in a dedicated thread. So make a blocking call.
        #
        self.response = self.plugin.request(self.last_request)
        self.req_end = time.time()

        log_info("{}: Completed request".format(self.name))

        # Raise signal as last step.
        self._raise_signal()     # Inform the completion

        # request thread terminates upon return.
        return


    def _chk_thread_done(self) -> bool:
        # Called from main thread to check on req thread if
        # completed or not.
        # Return false if running
        # Else thread is joined, cleared and any signal written
        # is cleared
        #
        if self.thr:
            if self.thr.is_alive():
                # Request thread has not completed yet.
                taken = time.time() - self.req_start
                log_error("{}:request running for {} > timeout{}".
                        format(self.name, take, self.request.timeout))
                return False

            # Join to formally close
            #
            self.thr.join(0)
            self.thr = None

        return True


    def handle_response(self):
        tnow = time.time()

        self._drain_signal()

        # Called from main thread, upon receiving signal
        # May be response or heartbeat from plugin
        #
        if not self.req_end:
            log_info("plugin_proc:{} req_end not set".format(this_proc_name))
            self.send_heartbeat()
            return

        if self.response == None:
            log_error("Internal error: Expect response")
            return 

        # Write response to backend server/engine.
        #
        clib_bind.write_action_response(self.response)
        self.response = None
        self.req_end = 0

        log_info("plugin_proc:{} plugin:{}: request taken:{} process-pause:{}".format(
            this_proc_name, self.name, time.time() - self.req_start, self.action_pause))


    def send_request(self, req:clib_bind.ActionRequest):
        # Called by main thread upon receiving request call to 
        # this plugin from the backend engine / server.
        #
        if not self._chk_thread_done():
            log_error("{}: request dropped as busy with previous".format(self.name))
            return

        if self.response:
            log_error("Internal error: request sent before response for last")
            return

        # Kick off thread to raise request to loaded plugin as blocking.
        #
        self.req_start = time.time()
        self.last_request = req
        self.thr = threading.Thread(target=self._run_request,
                name="req_{}".format(self.name))
        self.thr.start()

        log_info("{}: request submitted".format(self.name))

        return

    
    def shutdown(self):
        self.plugin.shutdown()



def handle_shutdown(active_plugin_holders: {}):
    global shutdown_request

    for name, holder in active_plugin_holders.items():
        holder.shutdown()
        log_info("Requested shutdown of action {}".format(name))

    shutdown_request = True
    return


def handle_server_request(active_plugin_holders: {}):

    # Loop until no more to read
    while True:
        ret, req = clib_bind.read_action_request(0)
        if not ret:
            log_info("No request from server") 
            break

        log_info("plugin_proc:{} server req: {}".format(this_proc_name, str(req)))
        if req.is_shutdown():
            handle_shutdown(active_plugin_holders)

        elif req.action_name in active_plugin_holders:
            plugin_holder = active_plugin_holders[req.action_name]
            if plugin_holder.is_valid():
                plugin_holder.send_request(req)
            else:
                log_error("{} is not in valid state to accept request".format(action_name))
        else:
            log_error("requested action {} is not loaded".format(action_name))
    return


def handle_plugin_holder(plugin_holder: LoMPluginHolder):
    plugin_holder.handle_response()
    return


def main_run(proc_name: str) -> int:
    global this_proc_name

    this_proc_name = proc_name
    
    pipe_list = {}
    active_plugin_holders = {}

    while not is_running_config_available():
        # Loop until we get the conf
        log_error("{}: Failing to get plugins for this proc".format(proc_name))
        time.sleep(10)


    plugins = get_proc_plugins_conf(proc_name)
    actions_conf = get_actions_conf()

    if not clib_bind.register_client(proc_name):
        log_error("Failing to register client {} with server".format(proc_name))
        return -1

    try:
        for name, path in plugins.items():
            conf = actions_conf.get(name, {})
            disabled = conf.get("disable", False)
            if not disabled:
                pluginHolder = LoMPluginHolder(name, path, conf)
                if pluginHolder.is_valid():
                    fdR, fdW = os.pipe()
                    pluginHolder.set_pipe(fdR, fdW)
                else:
                    log_error("Failed to register plugin {} from {}".format(
                        name, path))
                    return -1

                active_plugin_holders[name] = pluginHolder
                pipe_list[fdR] = name
            else:
                log_error("Skipped disabled plugin {}".format(name)) 
    except Exception as e:
        log_error("{}: plugin failure: exception:{}".format(proc_name, str(e)))

    if not pipe_list:
        log_error("No loaded plugin. Exiting. plugins:{}".format(plugins.keys()))
        return -1

    log_info("plugin_proc:{}: All {} plugins loaded. Into reading loop".
            format(proc_name, len(plugins)))

    while not signal_raised:
        ret = clib_bind.poll_for_data(list(pipe_list.keys()), POLL_TIMEOUT)

        if ret == -1:
            handle_server_request(active_plugin_holders)
            if shutdown_request:
                break
        elif ret >= 0:
            if not ret in pipe_list:
                log_error("INTERNAL ERROR: fd {} not in pipe list".format(ret))
            else:
                handle_plugin_holder(active_plugin_holders[pipe_list[ret]])
        elif ret != -2:
            # This is unexepected return value
            break


    log_info("plugin_proc:{} DONE. Exiting.".format(proc_name))
    # SIGHUP need a reload of everything.
    clib_bind.deregister_client(proc_name)

    if (not shutdown_request) and signal_raised:
        handle_shutdown(active_plugin_holders)
    return 0



def main(proc_name, global_rc_file):
    if global_rc_file:
        set_global_rc_file(global_rc_file)

    # Load plugin syspaths
    syspaths = get_global_rc().get("plugin_paths", [])
    for p in syspaths:
        rp = os.path.join(_CT_DIR, p)
        syspath_append(rp)

    syslog_init(proc_name)

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGHUP, signal_handler)
        signal.signal(signal.SIGUSR1, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    if not clib_bind.c_lib_init():
        log_error("Failed to init CLIB")
        return


    while (not shutdown_request) and (not sigterm_raised):
        if (main_run(proc_name) != 0):
            log_error("Exiting due to error")
            break
        if sigusr1_raised:
            log_info("Exiting upon SIGUSR1")
            break


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Args for Plugin process for Python plugins")
    parser.add_argument("-p", "--proc-name", required=True, 
            help="Name of this process. The config maps the plugins")
    parser.add_argument("-g", "--global-rc", default="", 
            help="Path of the global rc file")
    parser.add_argument("-t", "--test", action='store_true',
            help="Run in test mode", default=False)
    parser.add_argument("-l", "--log-level", type=int, default=3, help="set log level")
    args = parser.parse_args()

    if args.test:
        set_test_mode()

    set_log_level(args.log_level)

    main(args.proc_name, args.global_rc)


