#! /usr/bin/env python3


import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import common

# Test Anomaly
#

action_name = os.getenv("ACTION_NAME")
action_config = os.getenv("ACTION_CONFIG")
action_data = os.getenv("ACTION_DATA")
action_pause = os.getenv("ACTION_PAUSE")

class LoMPlugin:
    def getName(self) -> str:
        return action_name

    def __init__(:q





