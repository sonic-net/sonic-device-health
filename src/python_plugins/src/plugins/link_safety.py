#! /usr/bin/env python3

from swsscommon.swsscommon import events_init_subscriber, event_receive, event_receive_op_t
from common import *
from  gvars import *
import clib_bind
import subprocess

class LoMPlugin:
    def __init__(self, config: {}, fn_hb):
        self.name = "link_down"
        self.handle = events_init_subscriber()
        self.min = 80
        self.shutdown = False


    def getName(self) -> str:
        return self.name


    def is_valid(self):
        return True


    def request(self, req: clib_bind.ActionRequest) -> clib_bind.ActionResponse:
        d = json.loads(str(req))
        ctx = d.get(REQ_CONTEXT, {})
        link_data = json.loads(ctx.get("link_flap", "{}"))
        ifname = link_data.get("ifname", "")
        ret = 0
        ret_str = ""
        if ifname:
            up_cnt = subprocess.check_output("show int status | grep -v down | wc -l", shell=True) 
            down_cnt = subprocess.check_output("show int status | grep down | wc -l", shell=True) 
            res = 100 * float(int(up_cnt))/float(int(up_cnt)+int(down_cnt))
            if res >= self.min:
                ret_str = "{}: Has {}% up. Min: {}%".format(self.name, res, self.min)
        else:
            ret = -1
            ret_str = "{}: Missing ifname ctx={}".format(self.name, json.dumps(req.context))
        log_error("{}: ret={} ret_str={}".format(self.name, ret, ret_str))

        return clib_bind.ActionResponse(self.name, req.instance_id,
                req.anomaly_instance_id, req.anomaly_key, "", ret, ret_str)


    def shutdown(self):
        self.shutdown = True


