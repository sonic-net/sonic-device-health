#! /usr/bin/env python3

# TODO: Get anomaly key
import argparse
import importlib
import json
import os
import sys
import threading
import time
import uuid

_CT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_CT_DIR, "..", "src"))
sys.path.append(os.path.join(_CT_DIR, "lib"))

import gvars

POLL_TIMEOUT = 2
gvars.TEST_RUN = True

import test_client
from test_client import report_error

from common import *
import clib_bind
import helpers

TMP_DIR = os.path.join(_CT_DIR, "tmp")
cfg_dir = ""
TEST_DATA_FILE = os.path.join(_CT_DIR, "test_data", "test_data.json")

mitigation_lock = False

lst_procs = {}

def clean_dir(d):
    os.system("rm -rf {}".format(d))
    os.system("mkdir -p {}".format(d))
    log_info("Clean dir {}".format(d))
    return


def run_proc(proc_name: str, rcfile: str):
    # Running in Proc dedicated thread
    #
    module = importlib.import_module("plugin_proc")
    module.main(proc_name, rcfile)
    log_info("Returned from plugin_proc: proc={} rc={}".format(
        proc_name, rcfile))

def _load_procs(procs: [str], rcfile: str):
    for proc_name in procs:
        th = threading.Thread(target=run_proc, args=(proc_name, rcfile,),
                name="th_{}".format(proc_name))
        th.start()
        lst_procs[proc_name] = th
        log_info("Started proc={} rcfile={}".format(proc_name, rcfile))
    return


def write_conf(fl, d) -> {}:
    data = { k:v for k, v in d.items() if not k.startswith("_") }
    with open(fl, "w") as s:
        s.write(json.dumps(data, indent=4))
    return data


LockState_None = 0
LockState_Locked = 1
LockState_Pending = 2


class AnomalyHandler:
    def __init__(self, action_name:str, action_inp:{}, bindings:[]):
        self.test_run_cnt = action_inp.get("run_cnt", 1)
        self.mitigation_timeout = action_inp.get("mitigation_timeout", 60)
        self.test_run_index = 0
        self.test_instances = action_inp["instances"]
        self.test_instance_index = 0
        self.test_inst = None
        self.run_complete = False
        self.action_seq = [action_name] + bindings
        self.action_seq_index = 0
        self.instance_id_index = 0
        self.ct_instance_id = None
        self.anomaly_instance_id = None
        self.anomaly_key = ""
        self.anomaly_name = action_name
        self.anomaly_published = {}
        self.context = {}
        self.lock_state = LockState_None
        self.lock_exp = 0
        log_info("AnomalyHandler: {}: constructed".format(self.anomaly_name))


    def _get_ct_action_name(self) -> str:
        return self.action_seq[self.action_seq_index]


    def _get_inst_val(self, attr_name:str):
        action_name = self._get_ct_action_name()
        val = self.test_inst.get(action_name, {}).get(attr_name, None)
        if val != None:
            return val

        if attr_name == "run_cnt":
            return 1
        if attr_name == gvars.REQ_INSTANCE_ID:
            return str(uuid.uuid4())
        if attr_name == gvars.REQ_TIMEOUT:
            return 0        # No timeout
        if attr_name in [gvars.REQ_ACTION_DATA, gvars.REQ_CONTEXT,
                gvars.REQ_RESULT_CODE, gvars.REQ_RESULT_STR]:
            return None
        return None


    def start(self) -> bool:
        if self.run_complete:
            return False

        # Each test instance run start from anomaly action. Reset seq to 0
        self.action_seq_index = 0
        self.context = {}
        self.anomaly_instance_id = ""
        self.anomaly_key = ""
        self.anomaly_published = {}

        # Get current test instance
        self.test_inst = self.test_instances.get(str(self.test_instance_index), {})
        self.test_instance_index += 1
        if self.test_instance_index >= len(self.test_instances):
            self.test_instance_index = 0

        log_info("AnomalyHandler: Raise request to Anomaly {}".
                format(self.anomaly_name))
        self._write_request()
        return True


    def _write_request(self):
        # Send request to anomaly action
        self.ct_instance_id = self._get_inst_val(gvars.REQ_INSTANCE_ID)
        if not self.anomaly_instance_id:
            self.anomaly_instance_id = self.ct_instance_id

        req = { gvars.REQ_ACTION_REQUEST: {
            gvars.REQ_TYPE: gvars.REQ_TYPE_ACTION,
            gvars.REQ_ACTION_NAME: self._get_ct_action_name(),
            gvars.REQ_INSTANCE_ID: self.ct_instance_id,
            gvars.REQ_ANOMALY_INSTANCE_ID: self.anomaly_instance_id,
            gvars.REQ_ANOMALY_KEY: self.anomaly_key,
            gvars.REQ_CONTEXT: self.context,
            gvars.REQ_TIMEOUT: self._get_inst_val(gvars.REQ_TIMEOUT)}}
        test_client.server_write_request(req)
        return 


    def _do_publish(self, req:{}):
        helpers.publish_event(self.anomaly_name, req)


    def process_plugin_heartbeat(self, req:{}) -> bool:
        action_name = self._get_ct_action_name()
        if req[gvars.REQ_ACTION_NAME] != action_name:
            return False

        if req[gvars.REQ_INSTANCE_ID] != self.ct_instance_id:
            return False

        if not self.anomaly_published:
            data = req
        else:
            self.anomaly_published[gvars.REQ_MITIGATION_STATE] = gvars.REQ_MITIGATION_STATE_PROG
            data = self.anomaly_published

        data[gvars.REQ_HEARTBEAT] = str(time.time())
        self._do_publish(data)
        return True


    def _report_error_response(self, req:{}, msg:str):
        log_error("{}: msg:{} req:{}".format(msg,
            self.anomaly_name, json.dumps(req)))


    def process_plugin_response(self, req:{}) -> bool:
        action_name = self._get_ct_action_name()
        if req[gvars.REQ_ACTION_NAME] != action_name:
            return False

        if req[gvars.REQ_INSTANCE_ID] != self.ct_instance_id:
            return False

        log_info("AnomalyHandler: Read response {}: {}".format(
            self.anomaly_name, str(req)))

        # Validate  response
        if req[gvars.REQ_ANOMALY_INSTANCE_ID] != self.anomaly_instance_id:
            self._report_error_response("Mismatch in anomaly_instance ID{}".
                    format(self.anomaly_instance_id))

        if self.anomaly_key:
            if req[gvars.REQ_ANOMALY_KEY] != self.anomaly_key:
                self._report_error_response("Mismatch in anomaly_key {}".
                    format(self.anomaly_key))
        elif not req[gvars.REQ_ANOMALY_KEY]:
            self._report_error_response("Misssing anomaly_key")
        else:
            self.anomaly_key = req[gvars.REQ_ANOMALY_KEY]

        test_act_data = self.test_inst.get(action_name, {})
        for attr in [gvars.REQ_ACTION_DATA, gvars.REQ_RESULT_CODE,
                gvars.REQ_RESULT_STR]:
            val_expect = test_act_data.get(attr, None)
            if (val_expect != None) and (val_expect != ""):
                if req[attr] != val_expect:
                    _report_error_response("mismatch attr:{} exp:{}".
                            format(attr, val_expect))

        if not self.anomaly_published:
            self.anomaly_published = req
            self.anomaly_published[gvars.REQ_MITIGATION_STATE] = gvars.REQ_MITIGATION_STATE_INIT
            self._do_publish(self.anomaly_published)
        else:
            self._do_publish(req)

        # Are we done?
        seq_complete = False
        return_code = req[gvars.REQ_RESULT_CODE]
        return_str = req[gvars.REQ_RESULT_STR]

        if return_code != 0:
            # Force complete.
            seq_complete = True
        else:
            self.action_seq_index += 1
            seq_complete = self.action_seq_index >= len(self.action_seq)

        if not seq_complete and (self.action_seq_index == 1):
            # Start of mitigation sequence
            if self.lock_state == LockState_Locked:
                return_code = -1
                return_str = "Internal error: Thread has lock before start of mitigation"
                log_error(return_str)
                seq_complete = True
            else:
                if self.lock_state != LockState_None:
                    log_error("AnomalyHandler:{} Expect None lock state {}".format(
                        self.anomaly_name, self.lock_state))
                # Resume with lock acquired
                self.lock_state = LockState_Pending

        if (not seq_complete) and (self.lock_state == LockState_None):
            # lock has timedout
                return_code = -2
                return_str = "Mitigation lock timedout"
                log_error(return_str)
                seq_complete = True

        if seq_complete:
            # Release if any lock being held
            self._manage_lock(False)
            # Re-publish anomaly with completed state
            self.anomaly_published[gvars.REQ_RESULT_CODE] = return_code
            self.anomaly_published[gvars.REQ_RESULT_STR] = return_str
            self.anomaly_published[gvars.REQ_MITIGATION_STATE] = gvars.REQ_MITIGATION_STATE_DONE
            self._do_publish(self.anomaly_published)

            # increment run index, as are done with binding sequence.
            self.test_run_index += 1
            if self.test_run_index >= self.test_run_cnt:
                self.run_complete = True
                log_info("AnomalyHandler: Test run done for anomaly {} cnt: {}".
                        format(self.anomaly_name, self.test_run_cnt))
                return True

            # Restart the run
            log_info("AnomalyHandler: Read response {}: {}".format(self.anomaly_name))
            self.start()
            return True

        # Build context
        self.context[action_name] = req[gvars.REQ_ACTION_DATA]
        if self.lock_state == LockState_Locked:
            self._write_request()
            log_info("AnomalyHandler: {}: continue mitigation: {}: {}".format(
                self.anomaly_name, self.action_seq_index, self._get_ct_action_name))
        else:
            self.resume()


    def _manage_lock(self, acquire:bool):
        global mitigation_lock

        if acquire:
            if self.lock_state == LockState_Pending:
                if mitigation_lock:
                    # still lock is held by someone. Bail out
                    log_info("AnomalyHandler:{} lock pending".format(self.anomaly_name))
                    return False
                mitigation_lock = True
                self.lock_exp = int(time.time()) + self.mitigation_timeout
                self.lock_state = LockState_Locked
                return True
            else:
                return False
        elif self.lock_state == LockState_Locked:
            # release the lock
            mitigation_lock = False
            self.lock_exp = 0
            self.lock_state = LockState_None
            return True
        else:
            return False


    def resume(self) -> bool:
        if self._manage_lock(True):
            # Write request to next action in sequence
            self._write_request()
            log_info("AnomalyHandler: {}: start mitigation: {}".format(
                self.anomaly_name, self._get_ct_action_name))
            return True

        elif self.lock_exp and (int(time.time()) > self.lock_exp):
            self._manage_lock(False)
            self.anomaly_published[gvars.REQ_RESULT_CODE] = -3
            self.anomaly_published[gvars.REQ_RESULT_STR] = "Anomaly mitigation timeout"
            self.anomaly_published[gvars.REQ_MITIGATION_STATE] = gvars.REQ_MITIGATION_STATE_TIMEOUT
            self._do_publish(self.anomaly_published)


    def done(self)->bool:
        return self.run_complete

def run_a_testcase(test_case:str, testcase_data:{}, default_data:{}):
    global failed

    global_rc_data = {}

    global_rc_data = default_data.get("global_rc", {})
    if "global_rc" in testcase_data:
        # Overwrite provided keys from testcase.
        for k, v in test_data("global_rc").items():
            global_rc_data[k] = v
    
    if ((not global_rc_data) or (not testcase_data)):
        log_error("Missing data global_rc={} testcase_data={} test_case={}".format(
            len(global_rc_data), len(testcase_data), test_case))
        return

    # Get & create running dir; clean it if pre-exists.
    #
    cfg_dir = os.path.join(global_rc_data.get("config_running_path", TMP_DIR), test_case)
    clean_dir(cfg_dir)

    global_rc_data["config_running_path"] = cfg_dir

    # Read & write running config files.
    #
    procs_conf = write_conf(os.path.join(cfg_dir, global_rc_data["proc_plugins_conf_name"]),
            testcase_data["procs_config"])

    actions_conf = write_conf(os.path.join(cfg_dir, global_rc_data["actions_config_name"]),
            testcase_data["actions_config"])

    bindings_conf = write_conf(os.path.join(cfg_dir, global_rc_data["actions_binding_config_name"]),
            testcase_data["bindings_config"])

    write_conf(os.path.join(cfg_dir, global_rc_data["plugins_data_name"]),
            testcase_data.get("test_plugin_data", {}))

    global_rc_file = os.path.join(cfg_dir, global_rc_data["global_rc_name"])
    with open(global_rc_file, "w") as s:
        s.write(json.dumps(global_rc_data, indent=4))


    # Set test plugins data in globals
    # As plugins are loaded by another thread in the same process
    # they could access this.
    #

    for k, v in testcase_data.get("test_plugin_data", {}).items():
        if not k.startswith("_"):
            globals()[k] = v

    # Set paths for import
    syspath_append(_CT_DIR)
    syspath_append(os.path.join(_CT_DIR, "lib"))
    syspath_append(os.path.join(_CT_DIR, "plugins"))
    syspath_append(os.path.join(_CT_DIR, "..", "src"))

    # init clib after runnig config is ready
    set_global_rc_file(global_rc_file)
    clib_bind.c_lib_init()

    for path in global_rc_data["plugin_paths"]:
        # path can be absolute or relative to this filepath.
        syspath_append(os.path.join(_CT_DIR, path))

    _load_procs(list(procs_conf.keys()), global_rc_file)

    # All procs are loaded in dedicated threads.
    # They would have
    #   a. loaded associated plugins
    #   b. The client registrations for proc & plugins would be complete
    #      immediately buy asunchronoulsy via proc dedicated threads.
    #   c. The procs will be waiting for request from server.
    #

    # Expect all plugin-proc & plugins to have registered
    # Verify the same.
    #
    rcnt = 0
    for k,v in procs_conf.items():
        # Each proc creates a client registration + all actions registration
        rcnt = 1 + len(v)

    reg_conf = {}
    reg_exp = int(time.time()) + 10    # All registration must complete by 10 seconds
    while rcnt > 0:
        log_info("MAIN: Waiting for registrations rcnt={}".format(rcnt))
        tout = reg_exp - int(time.time())
        if tout < 0:
            tout = 0
        ret, data = test_client.server_read_request(tout)
        if not ret:
            report_error("Server: Pending registrations: Failed to read")
            break

        key = list(data)[0]
        val = data[key]
        if key == gvars.REQ_REGISTER_CLIENT:
            cl_name = test_client.parse_reg_client(val)
            if cl_name in reg_conf:
                report_error("Server: Duplicate registration by client {}".
                        format(cl_name))
                break

            reg_conf[cl_name] = []
            rcnt -= 1
            log_info("MAIN: Registered client {}".format(cl_name))

        elif key == gvars.REQ_REGISTER_ACTION:
            cl_name, action_name = test_client.parse_reg_action(val)
            if cl_name not in reg_conf:
                report_error("Server: register action:{} for missing client:{}".
                        format(cl_name, action_name))
                break
            lst = reg_conf[cl_name]
            if action_name in lst:
                report_error("Server: Duplicate registration for action {}/{}".
                        format(cl_name, action_name))
                break
            lst.append(action_name)
            rcnt -= 1
            log_info("MAIN: Registered client:{} action:{}".format(cl_name, action_name))
        else:
            report_error("server: In middle of vetting registration cnt={} req={}"
                    .format(rcnt, json.dumps(data, indent=4)))
            break

    if set(reg_conf.keys()) != set(procs_conf.keys()):
        report_error("server: proc registered={} != expected={}".format(
            set(reg_conf.keys()), set(procs_conf.keys())))
        return

    for cl_name, lst_actions in reg_conf.items():
        if set(procs_conf[cl_name].keys()) != set(lst_actions):
            report_error("client:{} action registered:{} != expected:{}".
                    format(cl_name, lst_actions, set(procs_conf[cl_name].keys())))
            return

    # all registrations arrived & verified.
    # Test run on actions

    test_input = testcase_data.get("test-main-run", {})
    test_run_conf = { k:v for k, v in test_input.items() if not k.startswith("_") }

    test_anomalies = {}
    for anomaly_action, v in test_run_conf.items():
        test_anomalies[anomaly_action] = AnomalyHandler(
                anomaly_action, v, bindings_conf[anomaly_action])

    log_info("Main: Starting anomaly handlers")
    for name, handler in test_anomalies.items():
        if not handler.start():
            report_error("Failed to start anomaly {}".format(name))
            return

    # Run while there is one or more active anomalies
    while test_anomalies:
        ret = False
        is_heartbeat = False

        # Read valid request
        while True:
            ret, req = test_client.server_read_request(POLL_TIMEOUT)
            if not ret:
                break
            elif (list(req)[0] == gvars.REQ_HEARTBEAT):
                req_data = req[gvars.REQ_HEARTBEAT]
                is_heartbeat = True
                break
            elif (list(req)[0] != gvars.REQ_ACTION_REQUEST):
                log_error("Internal error. Expected '{}': {}".format(
                    gvars.REQ_ACTION_REQUEST, json.dumps(req)))
            elif (req[gvars.REQ_ACTION_REQUEST][gvars.REQ_TYPE] !=
                    gvars.REQ_TYPE_ACTION):
                log_error("Internal error. Expected only {} from client {}".
                        format(gvars.REQ_ACTION_REQUEST, json.dumps(req)))
                # clients ony send response 
            else:
                req_data = req[gvars.REQ_ACTION_REQUEST]
                break

        # Process request. Loop until a handler accepts
        if ret:
            done = []
            for name, handler in test_anomalies.items():
                if is_heartbeat:
                    ret = handler.process_plugin_heartbeat(req_data)
                else:
                    ret = handler.process_plugin_response(req_data)
                    if ret:
                        if handler.done():
                            done.append(name)
                if ret:
                    # request processed
                    break
            # drop done anomalies from tracking
            for name in done:
                test_anomalies.pop(name, None)

        for name, handler in test_anomalies.items():
            # Try locking  if pending to proceed with mitigation
            # Release if curreht lock is expired.
            # No-op otherwise
            handler.resume()



    test_client.server_write_request({gvars.REQ_ACTION_REQUEST: {gvars.REQ_TYPE: gvars.REQ_TYPE_SHUTDOWN}})

    # Wait for a max 5 seconds for all procs to exit
    tstart = int(time.time())
    tout = 5
    texp = tstart + tout
    for proc, th in lst_procs.items():
        th.join(timeout=tout)
        tnow = int(time.time())
        if tnow > texp:
            tout = 0
        else:
            tout = texp - tnow

    # Report error on running processes as we can't
    # exit with thread running
    #
    while True:
        leak = False
        for proc, th in lst_procs.items():
            if th.is_alive():
                report_error("proc:{} not exiting for {} secs".
                        format(proc, int(time.time()) - tstart))
                leak = True
        if not leak:
            break
        time.sleep(1)

    for proc, th in lst_procs.items():
        th.join(0)

    return


def main():
    global TMP_DIR

    parser=argparse.ArgumentParser(description="Main test code")
    parser.add_argument("-p", "--path", default=TMP_DIR, help="test runtime path")
    parser.add_argument("-t", "--testcase", default="", help="test case name; Else all tests are run")
    parser.add_argument("-l", "--log-level", type=int, default=3, help="set log level")
    args = parser.parse_args()

    TMP_DIR = args.path

    set_log_level(args.log_level)

    test_data = {}
    default_data = {}
    with open(TEST_DATA_FILE, "r") as s:
        d = json.load(s)
        test_data = d.get("test_cases", None)
        default_data = d.get("default", None)

    if ((not test_data) or (not default_data) or 
            (args.testcase and (args.testcase not in test_data))):
        log_error("Unable to find testcase ({}) in {}".format(
            args.testcase, list(test_data.keys())))
        return

    helpers.publish_init("LoM_Test")

    test_cases = []
    if args.testcase:
        test_cases.append(args.testcase)
    else:
        test_cases = list(test_data.keys())

    for k in test_cases:
        log_info("**************** Running   testcase: {} ****************".format(k))
        run_a_testcase(k, test_data[k], default_data)
        log_info("**************** Completed testcase: {} ****************".format(k))


if __name__ == "__main__":
    threading.current_thread().name = "MAIN"
    main()

