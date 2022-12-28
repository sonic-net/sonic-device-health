#! /usr/bin/env python

import ctypes
import os
import sys
from typing import NamedTuple

# python_proc overrides this path via args, if provided.
GLOBAL_RC_FILE = "/etc/LoM/global.rc.json"
_CT_PATH = os.path.dirname(os.path.abspath(__file__))

from enum import Enum

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
#
# Global RC file default path is hardcoded.
# Path can be overridden via OS globals
#
# The RC file provides path that has running config
# running config for procs vs plugins, actions-config
# and binding config
#
# An external tool expected to generate based on static
# config files + tweaks from CONFIG-DB.
#
# First cut: running_path == static_path is True
# *******************************
#
_global_rc_data = {}

def get_global_rc() -> {}:
    if _global_rc_data:
        return global_rc_data

    if not os.path.exists(GLOBAL_RC_FILE):
        log_error("Missing global rc file {}".format(GLOBAL_RC_FILE))
        return {}

    d = {}
    with open(GLOBAL_RC_FILE, "r") as s:
        d = json.load(s)

    # required attributes
    reqd = { "config_running_path", "config_static_path", "proc_plugins_conf_name",
            "actions_config_name", "actions_binding_config_name"}

    if not reqd.issubset(set(d)):
        for i in reqd:
            if i not in d:
                print("Missing required attr {}".format(i))
        return {}


    _global_rc_data = {key:value for key, value in d.items() if not key.startswith("_")}
    return global_rc_data


def get_config_path(static = False) -> str:
    d = get_global_rc()
    if not d:
        return ""

    if static:
        return os.path.join(_CT_PATH, v["config-static-path"])
    else:
        return os.path.join(_CT_PATH, v["config-running-path"])


def get_proc_plugins_conf_file(static = False):
    # Return path for static/running path
    cfg_path = get_config_path(static)
    if not cfg_path:
        return ""
    fl = os.path.join(cfg_path, get_global_rc()["proc_plugins_conf_name"])
    if not os.path.exists(fl):
        return ""
    return fl



def get_actions_conf_file(static = False):
    # Return path for static/running path
    cfg_path = get_config_path(static)
    if not cfg_path:
        return ""
    fl = os.path.join(cfg_path, get_global_rc()["actions_config_name"])
    if not os.path.exists(fl):
        return ""
    return fl


def get_actions_binding_conf_file(static = False):
    # Return path for static/running path
    cfg_path = get_config_path(static)
    if not cfg_path:
        return ""
    fl = os.path.join(cfg_path, get_global_rc()["actions_binding_config_name"])
    if not os.path.exists(fl):
        return ""
    return fl


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

