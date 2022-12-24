#! /usr/bin/env python

import ctypes
import os
import sys
from typing import NamedTuple

GLOBAL_RC_FILE = "/etc/LoM/global.rc.json"
CT_PATH = os.path.dirname(os.path.abspath(__file__))

from enum import Enum

Vendor_subdir = "vendors"

class ActionType(Enum):
    ANOMALY = 0
    MITIGATION = 1
    SAFETYT_CHECK = 2


class ActionTypeStr(Enum):
    ANOMALY = "Anomaly"
    MITIGATION = "mitigation"
    SAFETYT_CHECK = "Safety-Check"

# *******************************
# Vendor related info
# *******************************
#
class vendorType(Enum):
    SONIC = "SONiC",
    CISCO = "Cisco",
    ARISTA = "Arista"
    UNKNOWN = "Unknown"


def get_vendor_type() -> vendorType:
    if os.path.exists("/etc/sonic"):
        return vendorType.SONIC
    return vendorType.UNKNOWN

def get_vendor_import_path():
    syspath.append(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        Vendor_subdir, get_vendor_type().value))


# *******************************
# Syspath updates.
# *******************************
#
def syspath_append(path:str):
    if path.endswith("/"):
        path = path[0:-1]

    if path not in sys.path:
        sys.path.append(path)



# *******************************
# Syslog related info
# *******************************
#
def syslog_init(proc_name:str):
    name = os.path.basename(sys.argv[0]) + "_" + proc_name
    syslog.openlog(name, syslog.LOG_PID)


def log_write(lvl: int, msg:str):
    syslog.syslog(lvl, msg)


def log_error(msg:str):
    syslog.syslog(syslog.LOG_ERR, msg)

def log_info(msg:str):
    syslog.syslog(syslog.LOG_INFO, msg)

def log_warning(msg:str):
    syslog.syslog(syslog.LOG_WARNING, msg)


# *******************************
# config related info
# *******************************
#
global_rc_data = {}

def read_global_rc() -> bool, {}:
    if global_rc_data:
        return True, global_rc_data

    if not os.path.exists(GLOBAL_RC_FILE):
        log_error("Missing global rc file {}".format(GLOBAL_RC_FILE))
        return False, {}

    d = {}
    with open(GLOBAL_RC_FILE, "r") as s:
        d = json.load(s)

    for i in [ "config_running_path", "config_static_path",
            "proc_plugins_conf_name", "actions_config_name", "actions_binding_config_name"]:
        if not d.get(i, None):
            return False, {}


    global_rc_data = {value:key for key, value in d.items()}
    return True, global_rc_data


def get_config_path(static = False) -> str:
    v, d = read_global_rc()
    if not v:
        return ""

    if static:
        return os.path.join(CT_PATH, v["config-static-path"])
    else:
        return os.path.join(CT_PATH, v["config-running-path"])


def get_proc_plugins_conf_file(static = False):
    # Return path for static/running path
    cfg_path = get_config_path(static)
    if not cfg_path:
        return ""
    return os.path.join(cfg_path, global_rc_data["proc_plugins_conf_name"])


def get_actions_conf_file(static = False):
    # Return path for static/running path
    cfg_path = get_config_path(static)
    if not cfg_path:
        return ""
    return os.path.join(cfg_path, global_rc_data["actions_config_name"])


def get_actions_binding_conf_file(static = False):
    # Return path for static/running path
    cfg_path = get_config_path(static)
    if not cfg_path:
        return ""
    return os.path.join(cfg_path, global_rc_data["actions_binding_config_name"])


def is_running_config_available() -> bool:
    if (get_proc_plugins_conf_file() and
            get_actions_conf_file() and
            get_actions_binding_conf_file()):
        return True
    else
        return False

        
def _get_data(fl:str) -> {}:
    ret = {}

    if fl and os.path.exists(fl):
        with open(fl, "r") as s:
            ret = json.load(s)
    return ret


def get_proc_plugins_conf(proc_name:str = "") -> {}:
    return _get_data(get_proc_plugins_conf_file()).get(proc_name, {})


def get_actions_conf() -> {}:
    return _get_data(get_actions_conf_file())


def get_actions_binding_conf(action_name:str) -> {}:
    d = _get_data(get_actions_binding_conf_file())
    if action_name:
        d = d.get(action_name, {})
    return d


# Action request attrs
ATTR_ACTION_NAME = "action_name"
ATTR_INSTANCE_ID = "instance_id"
ATTR_CONTEXT = "context"
ATTR_TIMEOUT = "timeout"
ATTR_ACTION_DATA = "action_data"
ATTR_RESULT_CODE = "result_code"
ATTR_RESULT_STR = "result_str"

