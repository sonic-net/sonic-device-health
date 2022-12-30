#! /usr/bin/env python3

#   Test Action
#   Hence completely customizable via Env variables
#   This can be used as reference for a plugin too.
#

import json
import os
import sys

from common import *
import test_client
import gvars
import clib_bind

# Test Anomaly
#

# TODO: "test_plugin_data" from testcase need to be added to actions-config
#
DEFAULT_RESP = { "foo": "bar", "IsOk": True }


class LoMPlugin:

    def __init__(self, config: {}, fn_hb):
        self.action_config = config
        self.action_name = self.action_config["action_name"]
        self.valid = True
        self.hb_callback = fn_hb
        self.shutdown_done = False
        self.req_idx = 0
        log_debug("test_action.py: LoMPlugin created for {}".format(self.action_name))
        

    def getName(self) -> str:
        return self.action_name


    def is_valid(self) -> bool:
        return self.valid and not self.shutdown_done

    
    def _get_resp(self) -> str:
        resp = self.action_config.get(gvars.REQ_ACTION_DATA, DEFAULT_RESP)
        return json.dumps(resp)


    def request(self, req: clib_bind.ActionRequest) -> clib_bind.ActionResponse:
        ret = clib_bind.ActionResponse (self.action_name, req.instance_id, _get_resp(), 0, "")

        if not self.valid:
            log_error("{}: Plugin is not valid. Failing request".format(action_name))
            ret.result_code = 1
            ret.result_str = "Plugin is not valid"

        elif req.action_name != self.action_name:
            log_error("{}: Mismatch in action name".format(self.action_name))
            ret.result_code = 2
            ret.result_str = "Mismatch in action name"
            
        # elif req.context != _get_global(gvars.REQ_CONTEXT, req.context):
            # log_error("{}: Mismatch in action name".format(self.action_name))
            # ret.result_code = 2
            # ret.result_str = "Mismatch in action name"
            
        elif not req.instance_id:
            log_error("{}: Missing instance id".format(action_name))
            ret.result_code = 3
            ret.result_str = "Misssing instance id"
            
        else:
            pause = int(self.action_config.get(gvars.REQ_PAUSE, 3))
            # hb_int = self.action_config.get(gvars.REQ_HEARTBEAT_INTERVAL, 1)
            inst_id = self.req.instance_id

            n = 0;
            while (not self.shutdown_done) and (n < pause):
                time.sleep(hb_int)
                self.hb_callback(inst_id)
                n += hb_int

        return ret


    def shutdown(self):
        # Request from main process on a different thread.
        # Use this to release resources
        # Don't block
        # if request is currently running, indicate the shutdown
        # so it could abort.
        #
        self.shutdown_done = True

