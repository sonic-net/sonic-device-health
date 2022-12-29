#! /usr/bin/env python3

import os
import sys
import test_client
from test_client import report_error

_CT_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(_CT_DIR, "..", "src")

from common import *
import gvars

TMP_DIR = os.path.join(_CT_DIR, "tmp")
cfg_dir = ""
TEST_DATA = os.path.join(_CT_DIR, "test_data", "test_data.json")


lst_procs = {}

def clean_dir(d):
    os.system("rm -rf {}".format(d))
    os.system("mkdir -p {}".format(d))
    return


def run_proc(proc_name: str, rcfile: str):
    # Running in Proc dedicated thread
    #
    module = importlib.import_module("plugin_proc")
    print("Calling plugin_proc: proc={} rc={}".format(
        proc_name, rcfile))
    module.main(proc_name, rcfile)
    print("Returned from plugin_proc: proc={} rc={}".format(
        proc_name, rcfile))

def load_procs(procs: [str], rcfile: str):
    for proc_name in procs:
        th = threading.Thread(target=run_proc, args=(proc_name, rcfile,))
        th.start()
        lst_procs[proc_name] = th
        print("Started proc={} rcfile={}".format(proc_name, rcfile))
    return


def write_conf(fl, d) -> {}:
    data = { k:v for k, v in d.items() if k not startswith("_") }
    with open(fl, w) as s:
        s.write(json.dumps(data, indent=4))
    return data


class AnomalyHandler:
    def __init__(self, action_name:str, action_inp:{}, bindings:[]):
        self.test_run_cnt = action_inp.get("run_cnt", 1)
        self.test_run_index = 0
        self.test_instances = action_inp["instances"]
        self.test_instance_index = 0
        self.test_inst = None
        self.done = False
        self.action_seq = [action_name] + bindings
        self.action_seq_index = 0
        self.instance_id_index = 0
        self.ct_instance_id = None


    def _get_ct_action_name() -> str:
        return self.action_seq[self.action_seq_index]


    def _get_inst_val(inst:{}, attr_name:str):
        action_name = _get_ct_action_name()
        val = self.test_inst.get(action_name, {}).get(attr_name, None)
        if val != None:
            return val

        if attr_name == "run_cnt":
            return 1
        if attr_name == REQ_INSTANCE_ID:
            idx = self.instance_id_index
            self.instance_id_index += 1
            return "id_{}_run_{}_idx_{}".format(self.action_seq[0],
                    self.run_index, idx)
        if attr_name == REQ_TIMEOUT:
            return 0        # No timeout
        if attr_name in [REQ_ACTION_DATA, REQ_CONTEXT, REQ_RESULT_CODE, REQ_RESULT_STR]:
            return None
        return None


    def start(self) -> bool:
        if self.done:
            return False

        # Each test instance run start from anomaly action. Reset seq to 0
        self.action_seq_index = 0

        # Get current test instance
        self.test_inst = self.test_instances.get(self.test_instance_index, {})
        self.test_instance_index += 1
        if self.test_instance_index > len(self.test_instances):
            self.test_instance_index = 0

        _write_request()


    def _write_request(self):
        # Send request to anomaly action
        self.ct_instance_id = _get_inst_val(gvars.REQ_INSTANCE_ID)
        server_write_request({ gvars.ACTION_REQUEST: {
            gvars.REQ_TYPE: gvars.REQ_TYPE_ACTION,
            gvars.REQ_ACTION_NAME: _get_ct_action_name(),
            gvars.REQ_INSTANCE_ID: self.ct_instance_id,
            gvars.REQ_CONTEXT: _get_inst_val(gvars.REQ_CONTEXT),
            gvars.REQ_TIMEOUT: _get_inst_val(gvars.REQ_TIMEOUT)}})
        return

    def process(self, req:{}) -> bool:
        action_name = _get_ct_action_name()
        if req[REQ_ACTION_NAME] != action_name:
            print("INFO: Skip mismathc Action {} != ct {}".format(
                req[REQ_ACTION_NAME], action_name))
            return False

        if req[REQ_INSTANCE_ID] != self.ct_instance_id:
            print("INFO: Skip mismatch instance-id {} != ct {}".format(
                req[REQ_ACTION_NAME], action_name))
            return False

        test_act_data = self.test_inst.get(action_name, {})
        for attr in [gvars.REQ_ACTION_DATA, gvars.REQ_RESULT_CODE,
                gvars.REQ_RESULT_Str]:
            val_expect = test_act_data.get(attr, None)
            if val_expect != None:
                if req[attr] != val_expect:
                    report_error("{}: mismatch attr:{} exp:{} != rcvd:{}".
                            format(action_name, attr, val_expect, req[attr]))

        # Are we done?
        self.test_run_index += 1
        if self.test_run_index >= self.test_run_cnt:
            self.done = True
            return True

        # Are we done with binding sequence
        self.action_seq_index += 1
        if self.action_seq_index >= len(self.action_seq):
            start()
            return True

        # Write request to next action in sequence
        _write_request()
        return True


    def done(self)->bool:
        return self.done


def run_a_testcase(test_case:str, test_data:{}, default_data:{}):
    global failed

    global_rc_data = {}
    failed = False

    global_rc_data = default_data.get("global_rc", {})
    if "global_rc" in test_data:
        # Overwrite provided keys from testcase.
        for k, v in test_data("global_rc").items():
            global_rc_data[k] = v
    
    testcase_data = test_data[test_case]

    if ((not global_rc_data) or (not testcase_data)):
        print("Missing data global_rc={} testcase_data={} test_case={}".format(
            len(global_rc_data), len(testcase_data), test_case))
        return

    # Get & create running dir; clean it if pre-exists.
    #
    cfg_dir = os.path.join(global_rc_data.get("config-running-path", TMP_DIR), test_case)
    clean_dir(cfg_dir)

    global_rc_data["config_running_path"] = cfg_dir

    # Read & write running config files.
    #
    procs_conf = write_conf(os.path.join(cfg_dir, global_rc_data["proc_plugins_conf_name"]),
            testcase_data["procs_config"])
    test_client.create_cache_services(len(procs_conf))

    actions_conf = write_conf(os.path.join(cfg_dir, global_rc_data["actions_config_name"]),
            testcase_data["actions_config"])

    bindings_conf = write_conf(os.path.join(cfg_dir, global_rc_data["actions_binding_config_name"]),
            testcase_data["bindings_config"])

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

    for path in testcase_data["plugin_paths"]:
        # path can be absolute or relative to this filepath.
        syspath_append(os.path.join(_CT_DIR, path)

    load_procs(test_data["procs_config"].keys(), global_rc_file)

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
    while rcnt > 0:
        ret, data = test_client.server_read_request()
        if not ret:
            report_error("Server: Pending registrations: Failed to read")
            break

        key = list(data)[0]
        val = data[key]
        if key == test_client.REGISTER_CLIENT:
            cl_name = parse_reg_client(val)
            if cl_name in reg_conf:
                report_error("Server: Duplicate registration by client {}".
                        format(cl_name))
                break

            reg_conf[cl_name] = []
            rcnt -= 1

        elif key == test_client.REGISTER_ACTION:
            cl_name, action_name = parse_reg_action(data)
            if cl_name in reg_conf:
                report_error("Server: register action:{} for missing client:{}".
                        format(cl_name, action_name))
                        format(cl_name))
                break
            lst = reg_conf[cl_name]
            if action_name in lst:
                report_error("Server: Duplicate registration for action {}/{}".
                        format(cl_name, action_name))
                break
            lst.append(action_name)
            rcnt -= 1
        else:
            report_error("server: In middle of vetting registration cnt={} req={}"
                    .format(rcnt, json.dumps(data, indent=4)))
            break

    if failed:
        return

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

    test_input = testcase_data.get("test-main-run", {}).get("input", {})
    test_run_conf = { k:v for k, v in test_input.items() if k not startswith("_") }

    test_anomalies = {}
    for anomaly_action, v in test_run_conf.items():
        test_anomalies[anomaly_action] = AnomalyHandler(
                anomalty_action, v, bindings_conf[anomaly_action])

    for k in test_anomalies:
        if not k.start():
            report_error("Failed to start anomaly {}".format(k))
            return

    while test_anomalies:
        ret = False
        while not ret:
            ret, req = test_client.server_read_request()
            if not ret:
                print("Error failed to read. Read again")
            elif list(req.keys()][0] != ACTION_REQUEST:
                print("Internal error. Expected ACTION_REQUEST: {}".format(json.dumps(req)))
                ret = False
            elif (req[ACTION_REQUEST][gvars.REQ_TYPE] !=
                    gvars.REQ_TYPE_ACTION):
                print("Internal error. Expected only {} from client".format(json.dumps(req)))
                ret = False

        done = []
        req_data = req[ACTION_REQUEST]

        for k in test_anomalies:
            if k.process(req_data):
                print("Processed read data")
                if k.done():
                    done.append(k)
                break
        for k in done:
            test_anomalies.pop(k, None)

    test_client.server_write_request({ACTION_REQUEST: {REQ_TYPE: REQ_TYPE_SHUTDOWN}})

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
        for proc, th in lst_procs:
            if th.is_alive():
                report_error("proc:{} not exiting for {} secs".
                        format(proc, int(time.time()) - tstart))
                leak = True
        if not leak:
            break
        time.sleep(1)

    return


def main():
    globals TMP_DIR

    parser=argparse.ArgumentParser(description="Main test code")
    parser.add_argument("-p", "--path", default=TMP_DIR, help="test runtime path")
    parser.add_argument("-t", "--testcase", default="", help="test case name; Else all tests are run")
    args = parser.parse_args()

    TMP_DIR = args.path

    test_data = {}
    default_data = {}
    with open(TEST_DATA, "r") as s:
        d = json.load(s)
        test_data = d.get("test_cases", None)
        default_data = d.get("default", None)

    if (not test_data) or (args.testcase not in test_data) or (not default_data):
        print("Unable to find testcase ({}) in {}".format(
            args.test_case, TEST_DATA))
        return

    test_cases = []
    if args.testcase:
        test_cases.append(args.testcase)
    else:
        test_cases = list(test_data["test_cases"].keys)

    for k in test_cases:
        print("**************** Running   testcase: {} ****************".format(k))
        run_a_testcase(k, test_data, default_data)
        print("**************** Completed testcase: {} ****************".format(k))


