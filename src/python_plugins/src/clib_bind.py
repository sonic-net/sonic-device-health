#! /usr/bin/env python3

from common import *
import gvars

# *******************************
# c-bindings related info
# *******************************
#

# TODO: Get list of error codes defined for various errors

# Set Clib .so file path here
CLIB_DLL_FILE = None

_clib_dll = None
_clib_get_last_error = None
_clib_get_last_error_str = None
_clib_register_client = None
_clib_deregister_client = None
_clib_register_action = None
_clib_touch_heartbeat = None
_clib_read_action_request = None
_clib_write_action_response = None
_clib_poll_for_data = None


def c_lib_init() -> bool:
    global _clib_dll
    global _clib_get_last_error, _clib_get_last_error_str, _clib_register_client
    global _clib_deregister_client, _clib_register_action, _clib_touch_heartbeat
    global _clib_read_action_request, _clib_write_action_response, _clib_poll_for_data

    if _clib_dll:
        return True

    if not gvars.TEST_RUN:
        try:
            _clib_dll = ctypes.CDLL(CLIB_DLL_FILE)
        except OSError as e:
            log_error("Failed to load CDLL {} err: {}".format(CLIB_DLL_FILE, str(e)))
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

            _clib_register_action = _clib_dll.register_action
            _clib_register_action.argtypes = [ c_char_p ]
            _clib_register_action.restype = c_int

            _clib_deregister_client = _clib_dll.deregister_client
            _clib_deregister_client.argtypes = [ c_char_p ]
            _clib_deregister_client.restype = c_int

            _clib_touch_heartbeat = _clib_dll.touch_heartbeat
            _clib_touch_heartbeat.argtypes = [ c_char_p, c_char_p ]
            _clib_touch_heartbeat.restype = c_int

            _clib_read_action_request = _clib_dll.read_action_request
            _clib_read_action_request.argtypes = []
            _clib_read_action_request.restype = c_char_p

            _clib_write_action_response = _clib_dll.write_action_response
            _clib_write_action_response.argtypes = [ c_char_p ]
            _clib_write_action_response.restype = c_int

            _clib_poll_for_data = _clib_dll.poll_for_data
            _clib_poll_for_data.argtypes = [ POINTER(c_int), c_int, c_int ]
            _clib_poll_for_data.restype = c_int

            # Update values in gvars.py
            _update_globals()

        except Exception as e:
            log_error("Failed to load functions from CDLL {} err: {}".
                    format(CLIB_DLL_FILE, str(e)))
            _clib_dll = None
            return False
    else:
        import test_client
        log_debug("clib in test mode")

        if not test_client.clib_init():
            log_error("Failed to init test_client.clib_init")
            return False

        _clib_get_last_error = test_client.clib_get_last_error
        _clib_get_last_error_str = test_client.clib_get_last_error_str
        _clib_register_client = test_client.clib_register_client
        _clib_deregister_client = test_client.clib_deregister_client
        _clib_register_action = test_client.clib_register_action
        _clib_touch_heartbeat = test_client.clib_touch_heartbeat
        _clib_read_action_request = test_client.clib_read_action_request
        _clib_write_action_response = test_client.clib_write_action_response
        _clib_poll_for_data = test_client.clib_poll_for_data
        _clib_dll = "Test mode"
        
    return True


def validate_dll():
    if not _clib_dll:
        log_error("CLib is not loaded. Failed.")
        return gvars.TEST_RUN
    return True


def get_last_error() -> (int, str):
    return _clib_get_last_error(), _clib_get_last_error_str()


def _print_clib_error(m:str, ret:int):
    err, estr = get_last_error()
    log_error("{}: ret:{} last_error:{} ({})".format(m, ret, err, estr))


def register_client(proc_id: str) -> bool:
    if not validate_dll():
        return False, {}

    ret = _clib_register_client(proc_id.encode("utf-8"))
    if ret != 0:
        log_error("register_client failed for {}".format(proc_id))
        return False
    return True


def register_action(action: str) -> bool:
    if not validate_dll():
        return False, {}

    ret = _clib_register_action(action.encode("utf-8"))
    if ret != 0:
        log_error("register_action failed {}".format(action))
        return False

    log_info("clib_bind: register_action {}".format(action))
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
        log_error("touch_heartbeat failed action:{} id:{}".format(action, instance_id))
        return False
    return True


# CLIB globals
def _get_str_clib_globals(name:str) -> str:
    return (c_char_p.in_dll(_clib_dll, name)).value.decode("utf-8")


def _update_globals():
    gvars.REQ_TYPE = _get_str_clib_globals("REQ_TYPE")
    gvars.REQ_TYPE_ACTION = _get_str_clib_globals("REQ_TYPE_ACTION")
    gvars.REQ_TYPE_SHUTDOWN = _get_str_clib_globals("REQ_TYPE_SHUTDOWN")

    gvars.REQ_ACTION_NAME = _get_str_clib_globals("REQ_ACTION_NAME")
    gvars.REQ_INSTANCE_ID = _get_str_clib_globals("REQ_INSTANCE_ID")
    gvars.REQ_CONTEXT = _get_str_clib_globals("REQ_CONTEXT")
    gvars.REQ_TIMEOUT = _get_str_clib_globals("REQ_TIMEOUT")
    gvars.REQ_ACTION_DATA = _get_str_clib_globals("REQ_ACTION_DATA")
    gvars.REQ_RESULT_CODE = _get_str_clib_globals("REQ_RESULT_CODE")
    gvars.REQ_RESULT_STR  = _get_str_clib_globals("REQ_RESULT_STR")

class ActionRequest:
    def __init__(sdata: str):
        data = json.loads(sdata)
        self.type = data[gvars.REQ_TYPE]
        self.action_name = data[gvars.REQ_ACTION_NAME]
        self.instance_id = data[gvars.REQ_INSTANCE_ID]
        self.context = data[gvars.REQ_CONTEXT]
        self.timeout = data[gvars.REQ_TIMEOUT]

    def is_shutdown(self) -> bool:
        return self.type == gvars.REQ_TYPE_SHUTDOWN


def read_action_request() -> (bool, ActionRequest):
    if not validate_dll():
        return False, {}

    req = _clib_read_action_request().decode("utf-8")

    if not req:
        e, estr = get_last_error()
        if e:
            log_error("read_action_request failed")
        return False, None

    return True, ActionRequest(req)



class ActionResponse:
    def __init__(action_name:str,
            instance_id:str,
            action_data: str,
            result_code:int,
            result_str:str) :
        self.data = json.dumps({
                gvars.REQ_ACTION_NAME: action_name,
                gvars.REQ_INSTANCE_ID: instance_id,
                gvars.REQ_ACTION_DATA: action_data,
                gvars.REQ_RESULT_CODE: result_code,
                gvars.REQ_RESULT_STR : result_str })

                
    def value(self) -> str:
        return self.data 


def write_action_response(res: ActionResponse) -> bool:
    if not validate_dll():
        return False

    ret = _clib_write_action_response(
            ActionResponse.value().encode("utf-8"))

    if ret != 0:
        log_error("write_action_response failed")
        return False

    return True


def poll_for_data(lst_fds: [int], timeout:int) -> int:
    if not validate_dll():
        return False

    if not gvars.TEST_RUN:
        return _clib_poll_for_data((c_int*len(lst_fds))(*lst_fds), len(lst_fds), timeout)
    else:
        return _clib_poll_for_data(lst_fds, len(lst_fds), timeout)


