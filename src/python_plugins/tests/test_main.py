#! /usr/bin/env python3

import os
import sys
import test_client

_CT_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(_CT_DIR, "..", "src")

from common import *

TMP_DIR = os.path.join(_CT_DIR, "tmp")
cfg_dir = ""
TEST_DATA = os.path.join(_CT_DIR, "test_data", "test_data.json")


lst_procs = {}

failed = False


def print_error(m):
    print("ERROR: {}".format(m))
    failed = True
    return


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
    print("Calling plugin_proc: proc={} rc={}".format(
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
        self.action_name = action_name
        self.timeout = action_inp.get("timeout", None)
        self.instances = action_inp["instances"]
        self.instance_index = 0
        self.done = False


    def start(self):
        inst = self.instances[self.instance_index]
        server_write_request({
            ATTR_REQUEST_TYPE: ACTION_REQUEST,
            ATTR_ACTION_NAME: self.action_name,
            ATTR_INSTANCE_ID: inst[ATTR_INSTANCE_ID],
            ATTR_CONTEXT: {},
            ATTR_TIMEOUT: inst[ATTR_TIMEOUT]})
        return

    def process(self, rd_data:{}):
        if rd_data 
        return


    def done(self)->bool:
        return self.done


def run_a_testcase(test_case:str, test_data:{}):
    global failed

    default_data = test_data.get("default", {})
    global_rc_data = {}
    failed = False

    global_rc_data = default_data.get("global_rc", {})
    if "global_rc" in test_data:
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
        ret, data = server_read_request()
        if not ret:
            print_error("Server: Pending registrations: Failed to read")
            break

        key = list(data)[0]
        val = data[key]
        if key == test_client.REGISTER_CLIENT:
            cl_name = parse_reg_client(val)
            if cl_name in reg_conf:
                print_error("Server: Duplicate registration by client {}".
                        format(cl_name))
                break

            reg_conf[cl_name] = []

        elif key == test_client.REGISTER_ACTION:
            cl_name, action_name = parse_reg_action(data)
            if cl_name in reg_conf:
                print_error("Server: register action:{} for missing client:{}".
                        format(cl_name, action_name))
                        format(cl_name))
                break
            lst = reg_conf[cl_name]
            if action_name in lst:
                print_error("Server: Duplicate registration for action {}/{}".
                        format(cl_name, action_name))
                break
            lst.append(action_name)
        else:
            print_error("server: In middle of vetting registration cnt={} req={}"
                    .format(rcnt, json.dumps(data, indent=4)))
            break

    if failed:
        return

    if reg_conf.keys() != procs_conf.keys():
        print_error("server: proc registered={} != expected={}".format(
            reg_conf.keys(), procs_conf.keys()))
        return

    for k, v in reg_conf.items():
        if set(list(procs_conf[k])) != set(v):
            print_error("client:{} action registered:{} != expected:{}".
                    format(k, v, list(procs_conf[k])))
            return

    # all registrations arrived & verified.
    # Test run on actions

    run_cnt_set = 1

    while run_cnt_set > 0:
        raise_anomaly_requests(bindings_conf)

    test_input = testcase_data.get("test-main-run", {}).get("input", {})
    test_run_conf = { k:v for k, v in test_input.items() if k not startswith("_") }

    test_anomalies = {}
    for k, v in test_run_conf.items():
        test_anomalies[k] = AnomalyHandler(k, v, bindings_conf[k])

    for k in test_anomalies:
        if not k.start():
            print_error("Failed to start anomaly {}".format(k))
            return

    while test_anomalies:
        req = server_read_request()
        done = []
        for k in test_anomalies:
            if not k.process(req):
                print_error("Failed to process anomaly {}".format(k))
                return
            if k.done():
                done.append(k)
        for k in done:
            test_anomalies.pop(k, None)

    server_write_request({ATTR_REQUEST_TYPE: SHUTDOWN})

    tstart = int(time.time())
    tout = 5
    texp = tstart + tout
    for proc, th in lst_procs:
        th.join(timeout=tout)
        tnow = int(time.time())
        if tnow > texp:
            tout = 0
        else:
            rout = texp - tnow


    while True:
        leak = False
        for proc, th in lst_procs:
            if th.is_alive():
                print_error("proc:{} not exiting".format(proc))
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
    with open(TEST_DATA, "r") as s:
        d = json.load(s)
        test_data = d.get(test_case, {})

    if not test_data:
        print("Unable to find testcase ({}) in {}".format(
            test_case, TEST_DATA))

    test_cases = []
    if args.testcase:
        test_cases.append(args.testcase)
    else:
        test_cases = list(test_data["test_cases"].keys)

    for k in test_cases:
        print("**************** Running   testcase: {} ****************".format(k))
        run_a_testcase(k, test_data)
        print("**************** Completed testcase: {} ****************".format(k))


