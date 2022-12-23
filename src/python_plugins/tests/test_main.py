#! /usr/bin/env python3

import os
import sys
import test_client

CT_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(CT_DIR, "..", "src")

from common import *

TMP_DIR = os.path.join(CT_DIR, "tmp")
cfg_dir = ""
TEST_DATA = os.path.join(CT_DIR, "test_data", "test_data.json")


lst_procs: [Thread] = []


def clean_dir():
    os.system("rm -rf {}".format(TMP_DIR))
    os.system("mkdir -p {}".format(TMP_DIR))
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
        lst_procs.append(th)
        print("Started proc={} rcfile={}".format(proc_name, rcfile))
    return


def write_conf(fl, d):
    data = { k:v for k, v in d.items() if k not startswith("_") }
    with open(fl, w) as s:
        s.write(json.dumps(data, indent=4))
    return len(data)


def run_a_testcase(test_case:str, test_data:{}):
    default_data = test_data.get("default", {})
    global_rc_data = {}

    global_rc_data = default_data.get("global_rc", {})
    if "global_rc" in test_data:
        for k, v in test_data("global_rc").items():
            global_rc_data[k] = v
    
    testcase_data = test_data[test_case]

    if ((not global_rc_data) or (not testcase_data)):
        print("Missing data global_rc={} testcase_data={} test_case={}".format(
            len(global_rc_data), len(testcase_data), test_case))
        return

    cfg_dir = os.path.join(global_rc_data.get("config-running-path", TMP_DIR), test_case)
    clean_dir(cfg_dir)

    global_rc_data["config_running_path"] = cfg_dir

    pcnt = write_conf(os.path.join(cfg_dir, global_rc_data["proc_plugins_conf_name"]),
            testcase_data["procs_config"])
    test_client.create_cache_services(pcnt)

    write_conf(os.path.join(cfg_dir, global_rc_data["actions_config_name"]),
            testcase_data["actions_config"])

    write_conf(os.path.join(cfg_dir, global_rc_data["actions_binding_config_name"]),
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

    syspath_append(CT_DIR)
    syspath_append(os.path.join(CT_DIR, "lib"))
    syspath_append(os.path.join(CT_DIR, "plugins"))
    syspath_append(os.path.join(CT_DIR, "..", "src"))

    load_procs(test_data["procs_config"].keys(), global_rc_file)

    # Main proc loaded in another thread
    # 

    # Expect all plugin-proc & plugins to have registered
    #




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
        run_a_testcase(k, test_data)


