#! /usr/bin/env python3

from enum import Enum
import os
import time
import threading

from common import *

# This module helps mock c-bindings calls to server.
# This enable a test code to act as server/engine
#
# Way it works:
#   The test code invokes the plugin_proc.py in a different thread.
#   When there are multiple procs multiple threads will be created as one per proc.
#   Each thread gets its own cache service instance using the trailing number in 
#   its name as index into list of pre-created cache service instances.
#
#   Each cache-service instance has two caches as one for each direction
#   Each cache instance has a pipe with two fds as one for read & write.
#   Main thread collects write fds from all cache instances for server to client
#   and collects rd fs from all client to server cache instances
#   These fds are used for signalling between main thread and the thread that owns
#   the cache instance.
#   Cache supports rd/wr index and read / write methods.
#
#   Any write, the main thread writes into all server to client instances.
#   It listens on signals from all collected rd fds and read from signalling
#   cache instances.
#
#   The test code acts as engine in main thread.
#
# All requests/responses across are saved in a list capped by size.
# Each side adding to list, signals the other via a pipe.
#

th_local = threading.local(()

CACHE_LIMIT = 10

shutdown = False

# requests
# These are between clib client & server, hence mocked here.
REGISTER_CLIENT = "register_client"
DEREGISTER_CLIENT = "deregister_client"
REGISTER_ACTION = "register_action"
HEARTBEAT = "heartbeat"
ACTION_REQUEST = "action_request"
ACTION_RESPONSE = "action_response"
SHUTDOWN = "shutdown"

ATTR_CLIENT_NAME = "client_name"
ATTR_REQUEST_TYPE = "request_type"


# Caches data in one direction with indices for nxt, cnt to relaize Q full
# state and data buffer.
#
class CacheData:
    def __init__(self, limit:ina, c2s:bool):
        self.limit = limit
        self.rd_index = 0
        self.wr_index = 0
        self.rd_cnt = 0
        self.wr_cnt = 0
        self.data: { int: {} } = {}
        self.c2s = c2s
        self.signal_rd, self.signal_wr = os.pipe()


        def get_signal_fd() -> int:
            return self.signal_rd


        def get_write_fd() -> int:
            return self.signal_wr


        def _drain_signal():
            while True:
                r, _, _ = select.select([self.signal_rd], [], [], 0)
                if self.signal_rd in r:
                    rd = os.read(self.signal_rd, 100)
                else:
                    break


    def _raise_signal():
        os.write(self.signal_wr, b"data")


    def write(self, data: {}) -> bool:
        # Test code never going to rollover. So ignore cnt rollover possibility.
        #
        if (self.wr_cnt - self.rd_cnt) > self.limit:
            self.data[self.wr_index] = data
            self.wr_index += 1
            if self.wr_index >= self.limit:
                self.wr_index = 0
            self.wr_cnt += 1
            _raise_signal()
            return True
       else:
           log_error("c2s:{} write overflow. dropped {}/{}".format(
               self.c2s, self.wr_cnt, self.rd_cnt))
           return False


    # read with optional timeout.
    # timeout =
    #   0 -- Return immediately with or w/o data
    #  <0 -- Block until data is available for read
    #  >0 -- Wait for these many seconds for data
    # 
    def read(self, timeout=-1) -> bool, {}:
        while (!shutdown and (timeout != 0) && (self.rd_cnt >= self.wr_cnt)):
            t = 2
            if (timeout > 0):
                if (timeout < t):
                    t = timeout 
                timeout -= t

            r, _, _ = select.select([self.signal_rd], [], [], t)
            if self.signal_rd in r:
                break

        _drain_signal()

        if self.rd_cnt < self.wr_cnt:
            # copy as other thread could write, upon rd_cnt incremented.
            #
            ret = ( k:v for k, v in self.data[self.rd_index])
            self.rd_index += 1
            if self.rd_index >= self.limit:
                self.rd_index = 0
            self.rd_cnt += 1
            return True, ret
        else:
            log_error("c2s:{} read empty. {}/{}".format(
                self.c2s, self.wr_cnt, self.rd_cnt))
            return False


class cache_service:
    def __init__(self, limit:int=CACHE_LIMIT):
        self.c2s = CacheData()
            os.write(self.signal_wr, b"data")
        self.s2c = CacheData()


    def write_to_server(self, d: {}) -> bool:
        return self.c2s.write(d)

    def write_to_client(self, d: {}) -> bool:
        return self.s2c.write(d)
    log_error("Write overflow  s2c limit={}".format(self.limit))
            return False

    def read_from_server(self, timeout:int = -1) -> bool, {}:
        return self.s2c.read(timeout)

    def read_from_client(self, timeout:int = -1) -> bool, {}:
        return self.c2s.read(timeout)

    def get_signal_fd(is_c2s:bool) -> int:
        if is_c2s:
            return self.c2s.get_signal_fd()
        else:
            return self.s2c.get_signal_fd()


    def get_write_fd(is_c2s:bool) -> int:
        if is_c2s:
            return self.c2s.get_write_fd()
        else:
            return self.s2c.get_write_fd()


cache_services = None
rd_fds = {}
wr_fds = {}


#
# Each Python plugin proc is created in its own thread.
# To simplify pre-create that many cache services
# Register client will take a service based on the number
# in its name <...>_<n> e.g "proc_0"
# The taken up service instance is saved in thread local
# Rest of the calls from this thread uses this instance.
#
def create_cache_services(cnt:int):
    global cache_services
    global rd_fds, wr_fds

    cache_services = cache_service[cnt]
    for i in range(cnt):
        p = cache_services[i]
        rd_fds[p.get_signal_fd(true)] = p
        wr_fds[p.get_write_fd(false)] = p


test_error_code = 0
test_error_str = ""


#
# Mocked clib client calls
#
def reset_error():en(r) > 0:
    break

    global error_code, error_str

    error_code = 0
    error_str = ""

def get_last_error() -> int:
    return error_code


def get_last_error_str() -> str:
    return error_str


def _is_initialized():
    return getattr(threadLocal, 'cache_svc', None) is not None


def register_client(cl_name: bytes) -> int:
    if _is_initialized():
        print("ERROR: Duplicate registration {}".format(cl_name))
        return

    l = cl_name.split("_")
    if len(l) <= 1:
        th_local.cache_svc = None
        print("Proc name must trail with _<n>")
        return

    th_local.cache_svc = cache_services[l[-1]]
    th_local.cl_name = cl_name
    th_local.actions = []

    th_local.cache_svc.write_to_server({
        REGISTER_CLIENT: {
            ATTR_CLIENT_NAME: cl_name.decode("utf-8") }})
        return


def deregister_client(cl_name: bytes) -> int:
    if not _is_initialized():
        print("deregister_client: ERROR: client not registered {}".format(cl_name))
        return

    th_local.cache_svc.write_to_server({
        DEREGISTER_CLIENT: {
            ATTR_CLIENT_NAME: cl_name.decode("utf-8") }})
    
    # Clean local cache
    th_local.cache_svc = None
    th_local.cl_name = None
    th_local.actions = None

    return


def register_action(action_name: bytes) -> int:
    if not _is_initialized():
        print("register_action: ERROR: client not registered {}".format(action_name))
        return

    if action_name in th_local.actions:
        print("ERROR: Duplicate registration {}".format(actrion_name))
        return

    th_local.cache_svc.write_to_server({
        REGISTER_ACTION: {
            ATTR_ACTION_NAME: action_name.decode("utf-8"),
            ATTR_CLIENT_NAME: th_local.cl_name }})
    return


def touch_heartbeat(action_name:bytes, instance_id: bytes):
    if not _is_initialized():
        print("touch_heartbeat: ERROR: client not registered {}".format(action_name))
        return

    if action_name not in th_local.actions:
        print("ERROR: Heartbeat from unregistered action".format(actrion_name))
        return

    th_local.cache_svc.write_to_server({
        HEARTBEAT: {
            ATTR_CLIENT_NAME: th_local.cl_name,
            ATTR_ACTION_NAME: action_name.decode("utf-8"),
            ATTR_INSTANCE_ID: instance_id.decode("utf-8") }})

 
def _read_req():
    if th_local.req:
        return

    ret, d = th_local.cache_svc.read_from_server()
    if not ret:
        req = d[ATTR_REQUEST_TYPE]
        act = d.get(ATTR_ACTION_NAME)
        if (((req == ACTION_REQUEST) and (act in th_local.actions)) or
                (req == SHUTDOWN)):
            th_local.req = d
        else:
            print("{}: skipped req {} {}".format(th_local.cl_name, req, act))
    else:
        print("{}: read failed ret={}".format(th_local.cl_name, ret))
    return


def read_action_request() -> bytes:
    if not _is_initialized():
        print("read_action_request: ERROR: client not registered")
        return

    _read_req()
    d = th_local.req
    th_local.req = {}
    return json.dumps(d).encode("utf-8")


def write_action_response(resp: bytes) -> int:
    if not _is_initialized():
        print("write_action_request: ERROR: client not registered")
        return

    d = json.loads(resp.decode("utf-8"))
    th_local.cache_svc.write_to_server(d)
    return 0


def _poll(rdfds:[], timeout: int) -> [int]:
    while (not shutdown):
        poll_wait = 2

        if (timeout >= 0):
            if (timeout < poll_wait):
                poll_wait = timeout
            timeout -= poll_wait
        
        r, _, _ = select.select(rdfds, [], [], poll_wait)
        if r:
            return r
        if timeout == 0:
            return -2


def poll_for_data(fds, cnt:int, timeout: int) -> int:
    if not _is_initialized():
        print("poll_for_data: ERROR: client not registered")
        return

    recv_signal_fd = th_local.cache_svc.get_signal_fd(False)
    lst = [ recv_signal_fd ] + list(fds)

    while (not shutdown):
        r = _poll(lst, timeout)
        if r[0] == recv_signal_fd:
            # Return only if action matches calling client.
            _read_req()
            if th_local.req:
                return -1
            # Continue to poll
        else:
            return r[0]


## Server side read/write wrappers

def server_read_request(timeout:int = -1) -> bool, {}:
    lst = list(rd_fds.keys())
    r = _poll(lst, timeout)

    ret, d = rd_fds[r[0]].read_from_client()
    if not ret:
        return False, {}
    if len(d) != 1:
        print("Internal error. Expected one key. ({})".format(json.dumps(d)))
        return False, {}
    return True, d



def server_write_request(data:{}):
    # Write is broadcast to all instances
    # The instances filter out requests for their actions
    #
    for _, svc in wr_fds:
        svc.write_to_client(data)
    return


def parse_reg_client(data: {}) -> str :
    return data[ATTR_CLIENT_NAME]


def parse_reg_action(data: {}) -> str, str :
    return data[ATTR_CLIENT_NAME], data[ATTR_ACTION_NAME]


def parse_heartbeat(data: {}) -> str, str, str :
    return (data[ATTR_CLIENT_NAME], 
            data[ATTR_ACTION_NAME], data[ATTR_INSTANCE_ID])

