#! /usr/bin/env python3

from swsscommon.swsscommon import events_init_subscriber, event_receive, event_receive_op_t
from common import *
import gvars
import clib_bind

class LoMPlugin:
    def __init__(self, config: {}, fn_hb):
        self.name = "link_down"
        self.handle = events_init_subscriber()
        self.shutdown = False


    def getName(self) -> str:
        return self.name


    def is_valid(self):
        return True


    def request(self, req: clib_bind.ActionRequest) -> clib_bind.ActionResponse:
        link_data = json.loads(req.context.get("link_flap", "{}"))
        ifname = link_data.get("ifname", "")
        ret = 0
        ret_str = ""
        if ifname:
            os.system("sudo config int shutdown {}".format(ifname))
            ret_str = "Brought down link {}".format(ifname)
        else:
            ret = -1
            ret_str = "Missing ifname ctx={}".format(json.dumps(req.context))
        log_error("ret={} ret_str={}".format(ret, ret_str))

        return clib_bind.ActionResponse(self.name, req.instance_id,
                req.anomaly_instance_id, req.anomaly_key, "", ret, ret_str)


    def shutdown(self):
        self.shutdown = True



