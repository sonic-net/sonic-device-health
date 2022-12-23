#! /usr/bin/env python3

from enum import Enum
import os
import time
import threading

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

class CLIENT_REQ_TYPE(Enum):
REGISTER_PROC = 0
REGISTER_PLUGIN = 1
DEREGISTER_PROC = 2
HEARTBEAT = 3
ACTION_RESP = 4
CLIENT_REQ_CNT = 5


class SERVER_REQ_TYPE(Enum):
ACTION_REQ = 0
SHUTDOWN = 1
SERVER_REQ_CNT = 2


shutdown = False

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


def register_client(cl_name: bytes) -> int:
    l = cl_name.split("_")
    if len(l) <= 1:
        th_local.cache_svc = None
        print("Proc name must trail with _<n>")
        return

    th_local.cache_svc = cache_services[l[-1]]
    th_local.cache_svc.write_to_server({
        "register_client": {
            "name": cl_name.decode("utf-8") }})
    return


def deregister_client(cl_name: bytes) -> int:
    th_local.cache_svc.write_to_server({
        "deregister_client": {
            "name": cl_name.decode("utf-8") }})

    return


def register_action(action_name: bytes) -> int:
    th_local.cache_svc.write_to_server({
        "register_action": {
            "name": action_name.decode("utf-8") }})
    return


def touch_heartbeat(action_name:bytes, instance_id: bytes):
    th_local.cache_svc.write_to_server({
        "register_action": {
            "name": action_name.decode("utf-8"),
            "instance_id": instance_id.decode("utf-8") }})

 
def read_action_request() -> bytes:
    ret, d = th_local.cache_svc.read_from_server()
    if not ret:
        log_error("Failed to read data ret={}".format(ret))
    return json.dumps(d).encode("utf-8")


def write_action_response(resp: bytes) -> int:
    d = json.loads(resp.decode("utf-8"))
    th_local.cache_svc.write_to_server(d)
    return 0


def poll_for_data(fds, cnt:int, timeout: int) -> int:
    lst = [ th_local.cache_svc.get_signal_fd(False) ] + list(fds)
    r, _, _ = select.select(list(fds), [], [], poll_wait)
    if r:
        if r[0] == recv_signal_fd:
            return -1
        else:
            return r[0]
    return -2
       

## Server side read/write wrappers

def server_read_request(timeout:int = -1) -> bool, {}:
    while not shutdown:
        r, _, _ = select.select(list(rd_fds.keys()), [], [], 2)
        if len(r) > 0:
            break

    ret, d = rd_fds[r[0]].read_from_client()
    if not ret:
        return "", {}
    if len(d) != 1:
        print("Internal error. Expected one key. ({})".format(json.dumps(d)))
        return "", {}
    return d[list(d.keys())[0]]



def server_write_request(data:{})->int:
    # Write is broadcast to all instances
    # The instances filter out requests for their actions
    #
    for _, svc in wr_fds:
        return svc.write_to_client(data)


