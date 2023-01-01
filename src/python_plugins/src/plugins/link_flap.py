#! /usr/bin/env python3

from swsscommon.swsscommon import events_init_subscriber, event_receive, event_receive_op_t
from common import *
import gvars
import clib_bind

class LoMPlugin:
    def __init__(self, config: {}, fn_hb):
        self.name = "link_flap"
        self.flap_int = 15
        self.flap_cnt = 2
        self.flaps = {}
        self.shutdown_flag = False
        self.hb_callback = fn_hb
        self.hb_int = config.get(gvars.REQ_HEARTBEAT_INTERVAL, 2)
        self.handle = events_init_subscriber(recv_timeout=(self.hb_int * 1000))


    def getName(self) -> str:
        return self.name


    def is_valid(self):
        return True


    def _get_resp(self, ifname, interval) -> str:
        return json.dumps({
            "ifname": ifname,
            "duration": interval,
            "cnt": self.flap_cnt
            })

    def request(self, req: clib_bind.ActionRequest) -> clib_bind.ActionResponse:
        while True and (not self.shutdown_flag):
            evt = event_receive_op_t()
            ret = event_receive(self.handle, evt)
            if (ret == 0) and (evt.key == 'sonic-events-swss:if-state'):
                if evt.params["status"] == "down":
                    ifname = evt.params["ifname"]
                    if not ifname in self.flaps:
                        self.flaps[ifname] = [ int(time.time()) ]
                    else:
                        self.flaps[ifname].append(int(time.time()))
                    lst = self.flaps[ifname]

                    while len(lst) > self.flap_cnt:
                        lst.pop(0)

                    if len(lst) == self.flap_cnt:
                        interval = lst[-1] - lst[0]
                        if interval <= self.flap_int:
                            log_error("reporting anomsaly for {}".format(ifname))
                            return clib_bind.ActionResponse(self.name, req.instance_id,
                                    req.anomaly_instance_id, ifname,
                                    self._get_resp(ifname, interval), 0, "")
            self.hb_callback(req.instance_id)



    def shutdown(self):
        self.shutdown_flag = True



