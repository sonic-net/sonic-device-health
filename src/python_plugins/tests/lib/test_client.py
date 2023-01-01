#! /usr/bin/env python3

from enum import Enum
import os
import select
import time
import threading

import gvars

from common import *

# This module helps mock c-bindings calls to server.
# This enable a test code to act as server/engine
#
# Way it works:
#   The test code invokes the plugin_proc.py in a different thread.
#   When there are multiple procs multiple threads will be created as one per proc.
#   Each thread gets its own cache service instance using the trailing number in 
#   its name as index into list of pre-created cache service instances.
#   The cache service mimics the R/W channels between main thread & proc.
#
#   Each cache-service instance has two caches as one for each direction
#   Each cache instance has a pipe with two fds as one for read & write.
#
#   Main thread owns caches from all services for server to client.
#   Proc thread owns cache for client to server.
#
#   Main thread collects write fds from all cache instances for server to client
#   and collects rd fs from all client to server cache instances
#   These fds are used for signalling between main thread and the thread that owns
#   the cache instance.
#   Cache supports rd/wr index and read / write methods.
#
#   Any write, the main thread writes into all server to client instances.
#   The client threads takes only requests meant for its actions
#
#   It listens on signals from all collected rd fds and read from signalling
#   cache instances.
#
#   This test code acts ass or mimics engine in the main thread.
#   In non-test scenario, the supervisord from container manages the processes
#   for each proc.
#
# All requests/responses across are saved in a list capped by size.
# Each side adding to list, signals the other via a pipe.
#

# Create this just once and use
# Each thread transparently gets its own copy
#
th_local = threading.local()

CACHE_LIMIT = 10

shutdown = False

def report_error(errMsg: str):
    log_error("ERROR: {}".format(errMsg))
    return


# Caches data in one direction with indices for nxt, cnt to relaize Q full
# state and data buffer.
#
SIGNAL_MSG = b"data"

class CacheData:
    def __init__(self, limit:int, c2s:bool):
        self.limit = limit
        self.rd_index = 0
        self.wr_index = 0
        self.rd_cnt = 0
        self.wr_cnt = 0
        self.data: { int: {} } = {}
        self.c2s = c2s      # True for client to server direction
        self.signal_rd, self.signal_wr = os.pipe()


    def get_signal_rd_fd(self) -> int:
        return self.signal_rd


    def get_signal_wr_fd(self) -> int:
        return self.signal_wr


    def _drain_signal(self):
        # Drain a single signal only
        r, _, _ = select.select([self.signal_rd], [], [], 0)
        if self.signal_rd in r:
            os.read(self.signal_rd, len(SIGNAL_MSG))


    def _raise_signal(self):
        os.write(self.signal_wr, SIGNAL_MSG)


    def write(self, data: {}) -> bool:
        # Test code never going to rollover. So ignore cnt rollover possibility.
        #
        if (self.wr_cnt - self.rd_cnt) >= self.limit:
            log_error("c2s:{} write overflow. dropped {}/{}".format(
                self.c2s, self.wr_cnt, self.rd_cnt))
            return False

        self.data[self.wr_index] = data
        self.wr_index += 1
        if self.wr_index >= self.limit:
            self.wr_index = 0
        self.wr_cnt += 1
        self._raise_signal()
        return True


    # read with optional timeout.
    # timeout =
    #   0 -- Return immediately with or w/o data
    #  <0 -- Block until data is available for read
    #  >0 -- Wait for these many seconds for data
    # 
    def read(self, timeout=-1) -> (bool, {}):
        while ((not shutdown) and (timeout != 0) and (self.rd_cnt >= self.wr_cnt)):
            t = 2
            if (timeout > 0):
                if (timeout < t):
                    t = timeout 
                timeout -= t

            r, _, _ = select.select([self.signal_rd], [], [], t)
            if self.signal_rd in r:
                break

        self._drain_signal()

        if self.rd_cnt < self.wr_cnt:
            # copy as other thread could write, upon rd_cnt incremented.
            #
            ret = { k:v for k, v in self.data[self.rd_index].items()}
            self.rd_index += 1
            if self.rd_index >= self.limit:
                self.rd_index = 0
            self.rd_cnt += 1
            return True, ret
        else:
            log_info("c2s:{} read empty. {}/{}".format(
                self.c2s, self.wr_cnt, self.rd_cnt))
            return False, {}


class cache_service:
    def __init__(self, limit:int=CACHE_LIMIT):
        # Get cache for both directions
        self.c2s = CacheData(limit, True)
        self.s2c = CacheData(limit, False)


    def write_to_server(self, d: {}) -> bool:
        return self.c2s.write(d)

    def write_to_client(self, d: {}) -> bool:
        return self.s2c.write(d)

    def read_from_server(self, timeout:int = -1) -> (bool, {}):
        return self.s2c.read(timeout)

    def read_from_client(self, timeout:int = -1) -> (bool, {}):
        return self.c2s.read(timeout)

    def get_signal_rd_fd(self, is_c2s:bool) -> int:
        if is_c2s:
            return self.c2s.get_signal_rd_fd()
        else:
            return self.s2c.get_signal_rd_fd()


    def get_signal_wr_fd(self, is_c2s:bool) -> int:
        if is_c2s:
            return self.c2s.get_signal_wr_fd()
        else:
            return self.s2c.get_signal_wr_fd()


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

    cache_services = [cache_service() for i in range(cnt)]

    for i in range(cnt):
        p = cache_services[i]
        rd_fds[p.get_signal_rd_fd(True)] = p
        wr_fds[p.get_signal_wr_fd(False)] = p


# TODO: Mimic error codes defined from clib_bind

test_error_code = 0
test_error_str = ""


#
# Mocked clib client calls
#
def reset_error():
    global test_error_code, test_error_str

    test_error_code = 0
    test_error_str = ""


def clib_init() -> bool:
    cnt = len(get_proc_plugins_conf())
    if (cnt <= 0) or (cnt > 100):
        log_error("Invalid count of proc entries cnt={}".format(cnt))
        return False
    create_cache_services(cnt)
    return True


def clib_get_last_error() -> int:
    return test_error_code


def clib_get_last_error_str() -> str:
    return test_error_str


def _is_initialized():
    return getattr(th_local, 'cache_svc', None) is not None


def clib_register_client(cl_name: bytes) -> int:
    if _is_initialized():
        report_error("Duplicate registration {}".format(cl_name))
        return -1

    l = cl_name.decode("utf-8").split("_")
    if len(l) <= 1:
        report_error("Proc name must trail with _<n>")
        return -1

    index = int(l[-1])
    if index >= len(cache_services):
        # Proc index must run from 0 sequentially as services
        # are created for count of entries in proc's conf.
        #
        report_error("Index {} > cnt {}".format(index, cnt))
        return -1

    log_info("Registered:{} taken service index {}".
            format(cl_name, index))
    th_local.cache_svc = cache_services[index]
    th_local.cl_name = cl_name.decode("utf-8")
    th_local.actions = []
    th_local.req = None

    th_local.cache_svc.write_to_server({
        gvars.REQ_REGISTER_CLIENT: {
            gvars.REQ_CLIENT_NAME: cl_name.decode("utf-8") }})
    return 0


def clib_deregister_client(cl_name: bytes) -> int:
    if not _is_initialized():
        report_error("deregister_client: client not registered {}".format(cl_name))
        return

    th_local.cache_svc.write_to_server({
        gvars.REQ_DEREGISTER_CLIENT: {
            gvars.REQ_CLIENT_NAME: cl_name.decode("utf-8") }})
    
    # Clean local cache
    th_local.cache_svc = None
    th_local.cl_name = None
    th_local.actions = None
    th_local.req = None

    return


def clib_register_action(action_name: bytes) -> int:
    if not _is_initialized():
        report_error("register_action: client not registered {}".format(action_name))
        return -1

    act_name = action_name.decode("utf-8")
    if act_name in th_local.actions:
        report_error("Duplicate registration {}".format(act_name))
        return -2

    th_local.actions.append(act_name)
    th_local.cache_svc.write_to_server({
        gvars.REQ_REGISTER_ACTION: {
            gvars.REQ_ACTION_NAME: act_name,
            gvars.REQ_CLIENT_NAME: th_local.cl_name }})
    return 0


def clib_touch_heartbeat(action_name:bytes, instance_id: bytes) -> int:
    if not _is_initialized():
        report_error("touch_heartbeat: client not registered {}".format(action_name))
        return -1

    name = action_name.decode("utf-8")
    if name not in th_local.actions:
        report_error("Heartbeat from unregistered action {}".format(name))
        return -1

    th_local.cache_svc.write_to_server({
        gvars.REQ_HEARTBEAT: {
            gvars.REQ_CLIENT_NAME: th_local.cl_name,
            gvars.REQ_ACTION_NAME: name,
            gvars.REQ_INSTANCE_ID: instance_id.decode("utf-8") }})
    return 0

 
def _read_req(timeout:int = -1) -> bool:
    if th_local.req:
        return True

    req = {}
    ret, req = th_local.cache_svc.read_from_server(timeout)
    if not ret:
        return False

    if ((len(req) != 1) or (list(req.keys())[0] != gvars.REQ_ACTION_REQUEST)):
        report_error("Expect ACTION_REQUEST req: {} {}".format(len(req), req.keys()))
        return False

    d = req[gvars.REQ_ACTION_REQUEST]
    if ((d["request_type"] != gvars.REQ_TYPE_SHUTDOWN) and
            (d[gvars.REQ_ACTION_NAME] not in th_local.actions)):
        report_error("unknown req/action {}".format(json.dumps(d)))
        return False

    th_local.req = req
    return True


def clib_read_action_request(timeout:int) -> bytes:
    if not _is_initialized():
        report_error("read_action_request: client not registered")
        return

    # read and also check if 
    ret = _read_req(timeout)
    if not ret:
        return b""

    req = json.dumps(th_local.req[gvars.REQ_ACTION_REQUEST]).encode("utf-8")
    th_local.req = None
    return req


def clib_write_action_response(resp: bytes) -> int:
    if not _is_initialized():
        report_error("write_action_request: client not registered")
        return

    th_local.cache_svc.write_to_server({
        gvars.REQ_ACTION_REQUEST: json.loads(resp.decode("utf-8"))})
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
            return []

    return []


# Called by client - here the Plugin Process
#
def clib_poll_for_data(fds:[int], cnt:int, timeout: int) -> int:
    if not _is_initialized():
        report_error("poll_for_data: client not registered")
        return

    recv_signal_fd = th_local.cache_svc.get_signal_rd_fd(False)
    lst = [ recv_signal_fd ] + list(fds)

    while (not shutdown):
        r = _poll(lst, timeout)
        if r:
            if recv_signal_fd in r:
                # Return only if action matches calling client.
                _read_req(0)
                if th_local.req:
                    return -1
                # Continue to poll
            else:
                return r[0]
        elif timeout > 0:
            return -2


## Server side read/write wrappers
# NOTE: These are not clib wrappers but match implementation
# of clib wrappers as server writes are read by clib mock and 
# vice versa

def server_read_request(timeout:int = -1) -> (bool, {}):
    lst = list(rd_fds.keys())
    r = _poll(lst, timeout)
    if not r:
        return False, {}

    ret, d = rd_fds[r[0]].read_from_client(0)

    if not ret:
        return False, {}
    if len(d) != 1:
        report_error("Internal error. Expected one key. ({})".format(json.dumps(d)))
        return False, {}
    if list(d.keys())[0] not in [ gvars.REQ_REGISTER_CLIENT, gvars.REQ_DEREGISTER_CLIENT,
            gvars.REQ_REGISTER_ACTION, gvars.REQ_HEARTBEAT, gvars.REQ_ACTION_REQUEST]:
        report_error("Internal error. Unexpected request: {}".format(json.dumps(d)))
        return False, {}

    return True, d



def server_write_request(data:{}) -> bool:
    # Write is broadcast to all instances
    # The instances filter out requests for their actions
    #
    if ((len(data) != 1) or (list(data)[0] != gvars.REQ_ACTION_REQUEST)):
        report_error("Expect key {} with JSON object of the req as val: {}".
                format(gvars.REQ_TYPE_ACTION, json.dumps(data)))
        return False

    for _, svc in wr_fds.items():
        svc.write_to_client(data)
    return True


def parse_reg_client(data: {}) -> str :
    return data[gvars.REQ_CLIENT_NAME]


def parse_reg_action(data: {}) -> (str, str):
    return data[gvars.REQ_CLIENT_NAME], data[gvars.REQ_ACTION_NAME]


def parse_heartbeat(data: {}) -> (str, str, str):
    return (data[gvars.REQ_CLIENT_NAME], 
            data[gvars.REQ_ACTION_NAME], data[gvars.REQ_INSTANCE_ID])

