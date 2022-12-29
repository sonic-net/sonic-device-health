#! /usr/bin/env python3

#   Test Action
#   Hence completely customizable via Env variables
#   This can be used as reference for a plugin too.
#

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', "src"))
import common

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import test_client

# Test Anomaly
#

# "test_plugin_data" from testcase is loaded as globals
# where key is action name.
# This may be used to tweak behavior
#
DEFAULT_RESP = { "foo": "bar", "IsOk": True }


class LoMPlugin:

    def __init__(self, config: {}, do_touch_hearbeat: Callable[[instance_id:str], None]):
        self.action_config = config
        self.action_name = self.action_config["action_name"]
        self.is_valid = True
        self.hb_callback = Callable
        self.shutdown = False
        self.req_idx = 0
        self.global_inp = globals().get(self.action_name, {})
        self.global_resp = self.global_inp.get(REQ_ACTION_DATA, {})
        

    def _get_global(attr_name:str, default:None) -> str:
        return self.global_inp.get(attr_name, default)


    def getName(self) -> str:
        return self.action_name


    def is_valid(self) -> bool:
        return self.is_valid and not self.shutdown

    
    def _get_resp() -> {}:
        resp = self.action_config.get(test_client.REQ_ACTION_DATA, DEFAULT_RESP)
        
        if self.global_resp:
            added = self.global_resp,get(str(self.req_idx), {})
            if added:
                for k, v in added.items():
                    resp[k] = v
            self.req_idx += 1
            if self.req_idx >= len(self.global_resp):
                self.req_idx = 0
        return resp


    def request(req: ActionRequest) -> ActionResponse:
        ret = ActionResponse (self.action_name, req.instance_id, _get_resp(), 0, ""))

        if not self.is_valid:
            log_error("{}: Plugin is not valid. Failing request".format(action_name))
            ret.result_code = 1
            ret.result_str "Plugin is not valid"

        elif req.action_name != self.action_name:
            log_error("{}: Mismatch in action name".format(self.action_name))
            ret.result_code = 2
            ret.result_str "Mismatch in action name"
            
        elif req.context != _get_global(test_client.REQ_CONTEXT, req.context):
            log_error("{}: Mismatch in action name".format(self.action_name))
            ret.result_code = 2
            ret.result_str "Mismatch in action name"
            
        elif not req.instance_id:
            log_error("{}: Missing instance id".format(action_name))
            ret.result_code = 3
            ret.result_str "Misssing instance id"
            
        else:
            pause = int(self.action_config.get(test_client.REQ_PAUSE, 3))
            hb_int = self.action_config.get(test_client.REQ_HEARTBEAT_INTERVAL, 1)
            inst_id = self.req.instance_id

            n = 0;
            while !self.shutdown and (n < pause):
                time.sleep(hb_int)
                self.hb_callback(inst_id)
                n += hb_int

        return ret


    def shutdown():
        # Request from main process on a different thread.
        # Use this to release resources
        # Don't block
        # if request is currently running, indicate the shutdown
        # so it could abort.
        #
        self.shutdown = True

