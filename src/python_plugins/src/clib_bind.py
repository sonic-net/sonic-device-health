#! /usr/bin/env python3

from common.py import *

# *******************************
# c-bindings related info
# *******************************
#

test_run = os.getenv("TESTMODE") != None
if test_run:
    import test_client
    log_debug("Running in test mode")


_clib_dll = None


def c_lib_init(fl: str) -> bool:
    global _clib_dll

    if not test_run:
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

        except Exception as e:
            log_error("Failed to load functions from CDLL {} err: {}".format(fl, str(e)))
            _clib_dll = None
            return False
    else:
        _clib_get_last_error = test_client.get_last_error
        _clib_get_last_error_str = test_client.get_last_error_str
        _clib_register_client = test_client.register_client
        _clib_deregister_client = test_client.deregister_client
        _clib_register_action = test_client.register_action
        _clib_touch_heartbeat = test_client.touch_heartbeat
        _clib_read_action_request = test_client.read_action_request
        _clib_write_action_response = test_client.write_action_response
        _clib_poll_for_data = test_client.poll_for_data
        _clib_dll = "Test mode"

    return True


def validate_dll():
    if not _clib_dll:
        log_error("CLib is not loaded. Failed.")
        return test_run
    return True


def get_last_error(): -> (err: int, errstr: str):
    return _clib_get_last_error(), _clib_get_last_error_str()


def print_clib_error(m:str, ret:int):
    err, estr = get_last_error()
    log_error({}: ret:{} last_error:{} ({})".format(m, ret, err, estr))


def register_client(proc_id: str) -> bool:
    if not validate_dll():
        return False, {}

    ret = _clib_register_client(proc_id.encode("utf-8"))
    if ret != 0:
        print_clib_error("register_client failed", ret)
        return False
    return True


def register_action(action: str) -> bool:
    if not validate_dll():
        return False, {}

    ret = _clib_register_action(action.encode("utf-8"))
    if ret != 0:
        print_clib_error("register_action failed", ret)
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

    req = _clib_read_action_request().decode("utf-8")

    if not req:
        e, estr = get_last_error()
        if e:
            print_clib_error("read_action_request failed", 0)
        return False, None

    d = json.loads(req)
    return True, ActionRequest(
            d.get(ATTR_ACTION_NAME, "")
            d.get(ATTR_INSTANCE_ID, "")
            d.get(ATTR_CONTEXT, "")
            d.get(ATTR_TIMEOUT, 0))



class ActionResponse:
    def __init__(action_name:str,
            instance_id:str,
            action_data: str,
            result_code:int,
            result_str:st) :
        self.action_name = action_name
        self.instance_id = instance_id
        self.action_data = action_data
        self.result_code = result_code
        self.result_str = result_str


def write_action_response(res: ActionResponse) -> bool
    if not validate_dll():
        return False

    ret = _clib_write_action_response(
            json.dumps({
                ATTR_ACTION_NAME: res.action_name,
                ATTR_INSTANCE_ID: res.instance_id,
                ATTR_ACTION_DATA: res.action_data,
                ATTR_RESULT_CODE: res.result_code,
                ATTR_RESULT_STR: res.result_str
            }).encode("utf-8"))

    if ret != 0:
        print_clib_error("write_action_response failed", ret)
        return False

    return True


def poll_for_data(lst_fds: list[int], timeout:int) -> int:
    if not validate_dll():
        return False

    return _clib_poll_for_data((c_int*len(lst_fds))(*lst_fds), len(lst_fds), timeout)


