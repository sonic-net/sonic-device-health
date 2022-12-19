#! /usr/bin/env python

import ctypes
import os
import sys
from typing import NamedTuple

GLOBAL_RC_FILE = "/etc/LoM/global.rc.json"

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
    sys.path.append(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        Vendor_subdir, get_vendor_type().value))


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
        return False, {}

    d = {}
    with open(GLOBAL_RC_FILE, "r") as s:
        d = json.load(s)

    for i in [ "config_root_path", "config_static_sub", "config_current_sub",
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
        return os.path.join(v["config_root_path"], v["config_static_sub"])
    else:
        return os.path.join(v["config_root_path"], v["config_current_sub"])


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


def get_proc_plugins_conf(lang:str = "", proc_name:str = "") -> {}:
    d = _get_data(get_proc_plugins_conf_file())
    if lang:
        d = d.get(lang, {})
        if proc_name:
            d = d.get(proc_name, {})
    return d


def get_actions_conf() -> {}:
    return _get_data(get_actions_conf_file())


def get_actions_binding_conf(action_name:str) -> {}:
    d = _get_data(get_actions_binding_conf_file())
    if action_name:
        d = d.get(action_name, {})
    return d


# *******************************
# c-bindings related info
# *******************************
#

_clib_dll = None

class C_ActionRequest(Structure):
    _fields_ = [
            ("action_name",ctypes.c_char_p),
            ("instance_id",ctypes.c_char_p),
            ("context",ctypes.c_char_p),
            ("timeout", ctypes.c_short)]

class C_ActionResponse(Structure):
    _fields_ = [
            ("action_name",ctypes.c_char_p),
            ("instance_id",ctypes.c_char_p),
            ("action_data",ctypes.c_char_p),
            ("result_code", ctypes.c_short),
            ("result_str",ctypes.c_char_p)]

def c_lib_init(fl: str) -> bool:
    global _clib_dll

    try:
        _clib_dll = ctypes.CDLL(fl)
    except OSError as e:
        log_error("Failed to load CDLL {} err: {}".format(fl, str(e)))
        return False

    try:
        _clib_get_last_error = _clib_dll.get_last_error
        _clib_get_last_error.argtypes = []
        _clib_get_last_error.restype = c_int

        _clib_get_last_error_str = _clib_dll.get_last_error_str
        _clib_get_last_error_str.argtypes = []
        _clib_get_last_error_str.restype = c_char_p

        _clib_register_client = _clib_dll.register_client
        _clib_register_client.argtypes = [ c_char_p ]
        _clib_register_client.restype = c_int

        _clib_register_plugin = _clib_dll.register_plugin
        _clib_register_plugin.argtypes = [ c_char_p ]
        _clib_register_plugin.restype = c_int

        _clib_deregister_client = _clib_dll.deregister_client
        _clib_deregister_client.argtypes = [ c_char_p ]
        _clib_deregister_client.restype = c_int

        _clib_touch_heartbeat = _clib_dll.touch_heartbeat
        _clib_touch_heartbeat.argtypes = [ c_char_p, c_char_p ]
        _clib_touch_heartbeat.restype = c_int

        _clib_read_action_request = _clib_dll.read_action_request
        _clib_read_action_request.argtypes = [ POINTER(C_ActionRequest) ]
        _clib_read_action_request.restype = c_int

        _clib_write_action_response = _clib_dll.write_action_response
        _clib_write_action_response.argtypes = [ POINTER(C_ActionResponse) ]
        _clib_write_action_response.restype = c_int

        _clib_poll_for_data = _clib_dll.poll_for_data
        _clib_poll_for_data.argtypes = [ POINTER(c_int), c_int, c_int ]
        _clib_poll_for_data.restype = c_int

    except Exception as e:
        log_error("Failed to load functions from CDLL {} err: {}".format(fl, str(e)))
        _clib_dll = None
        return False

    return True


def validate_dll():
    if not _clib_dll:
        log_error("CLib is not loaded. Failed.")
        return False
    return True


def print_clib_error(m:str, ret:int):
    err = _clib_get_last_error()
    estr = _clib_get_last_error_str()
    log_error({}: ret:{} last_error:{} ({})".format(m, ret, err, estr))


def register_client(proc_id: str) -> bool:
    if not validate_dll():
        return False, {}

    ret = _clib_register_client(proc_id.encode("utf-8"))
    if ret != 0:
        print_clib_error("register_client failed", ret)
        return False
    return True


def register_plugin(action: str) -> bool:
    if not validate_dll():
        return False, {}

    ret = _clib_register_plugin(action.encode("utf-8"))
    if ret != 0:
        print_clib_error("register_plugin failed", ret)
        return False
    return True


def deregister_client(proc_id: str):
    if not validate_dll():
        return False, {}

    _clib_deregister_client(proc_id.encode("utf-8"))


def touch_heartbeat(action: str, instance_id: str) -> bool:
    if not validate_dll():
        return False, {}

    ret = _clib_touch_heartbeat(action.encode("utf-8"), instance_id.encode("utf-8"))
    if ret != 0:
        print_clib_error("touch_heartbeat failed", ret)
        return False
    return True


class ActionRequest:
    def __init__(action_name:str="",
            instance_id:str,
            context: str,
            timeout:int) :
        self.action_name = action_name
        self.instance_id = instance_id
        self.context = context
        self.timeout = timeout


def read_action_request() -> bool, ActionRequest:
    if not validate_dll():
        return False, {}

    rt = C_ActionRequest()
    ret = _clib_read_action_request(rt)

    if ret != 0:
        print_clib_error("read_action_reques failed", ret)
        return False, {}

    return True, ActionRequest(
            rt.action_name.decode("utf-8"),
            rt.instance_id.decode("utf-8"),
            rt.context.decode("utf-8"),
            rt.timeout)



class ActionResponse:
    def __init__(action_name:str="",
            instance_id:str,
            action_data: str,
            result_code:int,
            result_str:str) :
        self.action_name = action_name
        self.instance_id = instance_id
        self.action_data = action_data
        self.result_code = result_code
        self.result_str = result_str


def write_action_response(res: ActionResponse) -> bool
    if not validate_dll():
        return False

    rt = C_ActionResponse(
            action_name = res.action_name.encode("utf-8"),
            instance_id = res.instance_id.encode("utf-8"),
            action_data = res.action_data.encode("utf-8"),
            result_code = res.result_code,
            result_str  = res.result_str.encode("utf-8"))

    ret = _clib_write_action_response(rt)

    if ret != 0:
        print_clib_error("write_action_response failed", ret)
        return False

    return True


def poll_for_data(lst_fds: list[int], timeout:int) -> int:
    if not validate_dll():
        return False

    return _clib_poll_for_data((c_int*len(lst_fds))(*lst_fds), len(lst_fds), timeout)


