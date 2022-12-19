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


class LoMPluginHolder:

    def __init__(self, name:str, plugin_file:str, config: {}):
        module_name = ".".join(plugin_file.split(".")[0:-1])
        self.plugin = None
        self.fdR = None
        self.fdW = None
        self.thr = None
        self.response = {}
        self.request = {}
        self.name = ""

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
        if not self.plugin:
            return False
        return True


    def do_touch_hearbeat(self, instance_id:str):
        touch_heartbeat(self.name, instance_id)


    def set_pipe(self, fdR:int, fdW:int):
        if self.fdW != None:
            raise LoMPluginHolderFailure("Internal: Duplicate set_pipe")

        self.fdW = fdW
        self.fdR = fdR
        return


    def _raise_signal(self):
        os.write(self.fdW, b"Hello")
        return


    def _run_request(self):
        # Running in a dedicated thread. So make a blocking call.
        #
        self.response = self.plugin.request(self.request)
        _raise_signal()
        log_info("{}: Completed request".format(self.name))
        return


    def handle_response(self):
        if not chk_thread:
            log_error("{}: Internal error: thread is not done in handle_response".format(
                self.name))
            return

        if not self.response:
            log_error("{}: Internal error: empty response".format(
                self.name))
            return

        write_action_response(self.response)


    def chk_thread(self) -> bool:
        if self.thr:
            if self.thr.is_alive():
                # Formal closing
                self.thr.join(0)
            if not self.thr.is_alive():
                self.thr = None

        # reset the signal, if any
        r, _, _ = select.select([fdR], [], [], 0)
        if fdR in r:
            os.read(fdR, 100)

        return self.thr == None


    def request(self, req:ActionRequest):
        
        if not chk_thread():
            log_error("{}: request dropped as busy with previous".format(self.name))
            return

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




def handle_server_request(active_plugins: {}):
    ret, req = read_action_request()
    if not ret:
        log_error("Failed to read server request upon poll") 
        return
     active_plugins[req.action_name].request(req)
     return


def handle_plugin(plugin: LoMPlugin):
    plugin->handle_response()
    return


def main_run(proc_name: str):

    pipe_list = {}
    active_plugins = {}

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
                plugin = LoMPluginHolder(name, path, conf)
                if plugin.isValid():
                    fdR, fdW = os.pipe()
                    plugin.set_pipe(fdR, fdW)
                else:
                    log_error("Failed to register plugin {} from {}".format(
                        name, path))

                active_plugins[name] = plugin
                pipe_list[fdR] = name
            else:
                log_error("Skipped disabled plugin {}".format(name)) 
    except Exception as e:
        log_error("{}: plugin failure: exception:{}".format(proc_name, str(e)))

    while not signal_raised:
        # 
        isRequest, fd = poll_for_data(list(pipe_list.keys()), POLL_TIMEOUT)

        if isRequest:
            handle_server_request(active_plugins)
        else:
            if not fd in pipe_list:
                log_error("INTERNAL ERROR: fd {} not in pipe list".format(fd))
            else:
                handle_plugin(pipe_list[fd])
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




    





