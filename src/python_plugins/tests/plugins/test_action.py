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

# Test Anomaly
#

# The behavior is controlled by global variables loaded by test main
# The following are used to construct name as <action name>_<one of var
# names below>
ACTION_REQ_CTX = "REQ_CONTEXT"      # matched with incoming context
ACTION_RESP_DATA = "ACTION_RESP"    # Response sent out for request
ACTION_PAUSE = "ACTION_PAUSE"       # Pause time before sending response

def get_global(action_name, attr_name, default=None):
    s = "{}_{}".format(action_name, attr_name)
    return globals().get(s, default)


class LoMPlugin:

    def __init__(self, config: {}, do_touch_hearbeat: Callable[[instance_id:str], None]):
        self.action_config = config
        self.action_name = self.action_config["action_name"]
        self.is_valid = True
        self.hb_callback = Callable
        self.shutdown = False
        

    def getName(self) -> str:
        return self.action_name


    def is_valid(self) -> bool:
        return self.is_valid and not self.shutdown



    def request(req: ActionRequest) -> ActionResponse:
        ret = ActionResponse (self.action_name, req.instance_id,
                get_global(self.action_name, ACTION_RESP_DATA, {"test" : "ok"}), 0, "")

        if not self.is_valid:
            log_error("{}: Plugin is not valid. Failing request".format(action_name))
            ret.result_code = 1
            ret.result_str "Plugin is not valid"

        elif req.action_name != self.action_name:
            log_error("{}: Mismatch in action name".format(self.action_name))
            ret.result_code = 2
            ret.result_str "Mismatch in action name"
            
        elif req.context != get_global(self.action_name, ACTION_REQ_CTX, req.context):
            log_error("{}: Mismatch in action name".format(self.action_name))
            ret.result_code = 2
            ret.result_str "Mismatch in action name"
            
        elif not req.instance_id:
            log_error("{}: Missing instance id".format(action_name))
            ret.result_code = 3
            ret.result_str "Misssing instance id"
            
        else:
            pause = int(get_global(self.action_name, ACTION_PAUSE, 3))
            hb_int = self.action_config.get("heartbeat_interval", 1)
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

