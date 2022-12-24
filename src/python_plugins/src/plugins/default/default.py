NEED A revisit

#! /usr/bin/env python3

from collections.abc import Callable
import json
import os
import sys

import common

# A sample plugin code
# 
# Each plugin is for a single action, which can be detection / 
# mitigation / safety-check
# 
# Each plugin create a class as below with shown methods.
# 
# Multiple plugins could be loaded by a single process.
# A plugin is running until de-ini is called.
# 
# The process division is by sub-dir. All plugins in one sub-dir
# is managed by a process.
# 
# 

ACTION_NAME = "sample default"
ACTION_TYPE = common.ActionType.ANOMALY.value
ACTION_VERSION = "0.0.0"

class LoMPlugin:
    # The base class implemented by every plugin
    #

    # Return name of the action this plugin implements.
    #
    def getName(self) -> str:
        return ACTION_NAME

    def getType(self) -> int:
        return ACTION_TYPE

    def getVersion(self) -> str:
        return ACTION_VERSION


    # This method is called once upon plugin load, before
    # calling any other request except getName.
    # Note: Called only once at the start.
    # It is provided with config per schema for this action.
    #
    def init(self, config: {}) -> int:
        # "config is the JSON object of plugin per schema of the
        # corresponding action.
        #
        for k,v in config.items():
            print("Config key:{} val:{}".format(k,v))
        print("********* INIT complete **********")
        return 0


    # This method is called as last method before
    # unloading the plugin. No other API is called
    # after this method.
    # Use this to do all cleanup, resources release, ...
    # If you have some thread running, please terminate
    # as that could block plugin unload.
    #
    def deinit(self):
        # Release any resources. Do all cleanup.
        # Plugin will be released after this call.
        #
        print("******** DE-INIT complete ********")
        return

    # This is the main method that executes the action.
    # This is called only after init, which provides all the
    # required config.
    # The context for this action is provided as dict of
    # JSON object with key as sequence and data as provided
    # by previous.
    #
    # Input:
    #   instance_id - ID assigned to this run of the action
    #       The action may include it in its logs to denote
    #       from which instance run, this log is coming.
    #
    #   heartbeat - Long running requests are expected to
    #       callback this function every heartbeat-interval.
    #       Callable returns boolean
    #       If returns false, the request API must cleanup
    #       and return immediately.
    #
    #   heartbeat_interval - Max period between two heartbeat
    #       calls.
    #
    #   timeout - Max period for the call to complete.
    #       0 - 0 value implies no time limit
    #       > 0 - Sets max timeout in seconds
    #       < 0 - not expected and error.
    #
    # context:
    #   Dict - a collection of o/p from preceding actions
    #
    #   {
    #       <seq>: <action data>,
    #       ...
    #   }
    #   Action data is as published by that action.
    #
    # Output:
    #   O/p from this action
    #   It may only include, result, result-code and action
    #   specific data
    #
    def request(self, instance_id: str, context: {},
            heartbeat:Callable, heartbeat_interval:int,
            timeout:int) -> {}:
        # plugin request timeout value is part of config.
        # Complete before it.
        # Request taking longer than timeout will be aborted.
        # The abor is accomplished via thread by killing thread
        # that is blocked on this request.
        # 
        # Be ready to handle abort scenario. If this aborted
        # request may leave behind some state, the next request
        # should be ready to clean it and start new.
        #
        for k,v in context.items():
            print("Context key:{} val:{}".format(k,v))
        print("******* REQUEST complete *********")
        d = {
           ACTION_NAME: {
               "result-code": 0,
               "result-string": "All good",
               "myData": "Default"
            }
        }
        return d


    # A request call as above could be long running.
    # Caller may call it in a thread.
    # Caller could request for abort via this method.
    # The plugin may set some local flag that request watches
    # periodically.
    def abort(self):
        # Set needed flag to terminate any currently active API
        #
        return



def main():
    t = LoMPlugin();

    print("Name:{}".format(t.getName()))
    print("Type:{}".format(t.getType()))

    print("Call Init")
    t.init({"foo": "bar", "timeout": 5 })
    print("------------------------")

    print("Call Request")
    t.request("UUID-0", {"Reqfoo": "Reqbar", "xxx": 8 })
    print("------------------------")

    print("Call Deinit")
    t.deinit()
    print("------------------------")


if __name__ == "__main__":
    main()




    

