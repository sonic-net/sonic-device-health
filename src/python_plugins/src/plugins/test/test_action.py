#! /usr/bin/env python3

#   Test Action
#   Hence completely customizable via Env variables
#   This can be used as reference for a plugin too.
#

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import common

# Test Anomaly
#

action_name = os.getenv("ACTION_NAME")
action_config_str = os.getenv("ACTION_CONFIG")
action_req_ctx = os.getenv("ACTION_REQ")
action_resp_data = os.getenv("ACTION_RESP")
action_pause_str = os.getenv("ACTION_PAUSE")

def get_string_to_dict(jval:str) -> {}:
    ret = {}
    if jval:
        try:
            ret = json.loads(jval)
        except Exception as e:
            log_error("Failing to parse ({}). err({})".format(jval, str(e)))
    return ret


def get_string_to_int(jval:str, def_val:int) -> int:
    ret = def_val
    if str:
        try:
            ret = int(jval)
        except Exception as e:
            log_error("Failing int({}) err:({})".format(jval, str(e)))
    return ret

            

class LoMPlugin:

    def __init__(self, config: {}, do_touch_hearbeat: Callable[[instance_id:str], None]):
        self.action_config = get_string_to_dict(action_config_str)
        self.is_valid = True
        self.hb_callback = Callable
        
        for k, v in self.action_config:
            if config.get(k, None) != v:
                self.is_valid = False


    def getName(self) -> str:
        return action_name


    def is_valid(self) -> bool:
        return self.is_valid



    def request(req: ActionRequest) -> ActionResponse:
        ret = ActionResponse (action_name, req.instance_id, action_resp_data, 0, "")

        if not self.is_valid:
            log_error("{}: Plugin is not valid. Failing request".format(action_name))
            ret.result_code = 1
            ret.result_str "Plugin is not valid"

        elif req.name != action_name:
            log_error("{}: Mismatch in action name".format(action_name))
            ret.result_code = 2
            ret.result_str "Mismatch in action name"
            
        elif not req.instance_id:
            log_error("{}: Missing instance id".format(action_name))
            ret.result_code = 3
            ret.result_str "Misssing instance id"
            
        else:
            pause = get_string_to_int(action_pause_str, 0)
            hb_int = self.action_config.get(heartbeat-interval, 0)
            inst_id = self.req.instance_id

            n = 0;
            while n < pause:
                time.sleep(hb_int)
                self.hb_callback(inst_id)
                n += hb_int

        return ret






