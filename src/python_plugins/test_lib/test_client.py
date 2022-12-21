#! /usr/bin/env python3

import os
import time

test_error_code = 0
test_error_str = ""

test_registered_client: str = None
test_registered_actions: [str] = None
test_heart_beat: {str: int} = None
test_req_to_send: str = None
test_resp_received: str = None

send_signal_fd = None
recv_signal_fd = None

def _raise_signal(m:str):
    if send_signal_fd == None:    
        print("send_signal_fd is not available")
    os.write(send_signal_fd, "{}:{}".format(m, str(int(time.time()))).encode("utf-8"))


_lst_globals = { k:v for k, v in list(globals().items()) if k.startswith("test_") }

def _reset_all():
    for k in _lst_globals:
        globals()[k] = None


def reset_error():
    global error_code, error_str

    error_code = 0
    error_str = ""


def get_last_error() -> int:
    return error_code


def get_last_error_str() -> str:
    return error_str


def register_client(cl_name: bytes) -> int:
    global registered_client

    if registered_client:
        log_error("Re-registering client")
    else:
        registered_client = cl_name.decode("utf-8")
        _raise_signal("register_client")

    return


def deregister_client(cl_name: bytes) -> int:
    global registered_client

    cl = cl_name.decode("utf-8")

    if not registered_client:
        log_error("No client to de-register")
    elif registered_client != cl:
        log_error("deregister: client name mismatch")
    else:
        registered_client = None
        _raise_signal("deregister_client")

    return


def register_action(action_name: bytes) -> int:
    global registered_client, test_registered_actions

    if test_registered_actions == None:
        test_registered_actions = []

    if not registered_client:
        log_error("register_action: client yet to register. action".format(action_name)")
    elif action_name in test_registered_actions:
        log_error("register_action: duplicate {}".format(action_name))
    else:
        test_registered_actions.append(action_name.decode("utf-8"))
        _raise_signal("register_action")

    return


def touch_heartbeat(action_name:bytes, instance_id: bytes):
    global test_heart_beat

    if ((not test_registered_actions) or (action_name not in test_registered_actions)):
        log_error("touch_heartbeat action not registered yet")
    else:
        if test_heart_beat == None:
            test_heart_beat = {}
        test_heart_beat[action_name] = test_heart_beat.get(action_name, 0) + 1
        _raise_signal("touch_heartbeat")

 
def read_action_request() -> bytes:
    rd = os.read(recv_signal_fd, 100)
    print("client: Received signal: {}".format(rd.decode("utf-8")))
    return test_req_to_send.encode("utf-8")


def write_action_response(resp: bytes) -> int:
    test_resp_received = resp.decode("utf-8")
    _raise_signal("write_action_response")
    return 0


def poll_for_data(fds, cnt:int, timeout: int) -> int:
    lst = [ recv_signal_fd ] + list(fds)
    r, _, _ = select.select(list(fds), [], [], poll_wait)
    if r:
        if r[0] == recv_signal_fd:
            return -1
        else:
            return r[0]
    return -2
       















