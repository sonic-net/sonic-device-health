#! /usr/bin/env python3

# Way to test plugins as standalone
#
import sys

sys.path.append("..")
import clib_bind
from common import *
from gvars import *
import link_flap
import link_safety
import link_down

def hb(id:str):
    print("hb({}) called".format(id))
    return


req = clib_bind.ActionRequest(json.dumps({
    REQ_TYPE: REQ_TYPE_ACTION,
    REQ_ACTION_NAME: "link_flap",
    REQ_INSTANCE_ID: "inst_0_flap",
    REQ_ANOMALY_INSTANCE_ID: "inst_0_flap",
    REQ_ANOMALY_KEY: "ethernet92",
    REQ_CONTEXT: {},
    REQ_TIMEOUT: 0 }))


flap_plugin = link_flap.LoMPlugin({}, hb)

res = flap_plugin.request(req)

print("req={}".format(str(req)))
print("res={}".format(str(res)))

d = json.loads(str(res))
anomaly_key = d.get(REQ_ANOMALY_KEY, "NOne")
action_data = d.get(REQ_ACTION_DATA, "")
print("*************** key={} data={}".format(anomaly_key, str(action_data)))

safety_plugin = link_safety.LoMPlugin({}, hb)

print("")
print("----------------------------------------------")
print("")
sreq = clib_bind.ActionRequest(json.dumps({
    REQ_TYPE: REQ_TYPE_ACTION,
    REQ_ACTION_NAME: "link_safety",
    REQ_INSTANCE_ID: "inst_0_safety",
    REQ_ANOMALY_INSTANCE_ID: "inst_0_flap",
    REQ_ANOMALY_KEY: anomaly_key,
    REQ_CONTEXT: {"link_flap": action_data },
    REQ_TIMEOUT: 0 }))

print("safety: sreq={}".format(str(sreq)))

sres = safety_plugin.request(sreq)

print("safety: sres={}".format(str(sres)))

link_down_plugin = link_down.LoMPlugin({}, hb)

print("")
print("----------------------------------------------")
print("")
dreq = clib_bind.ActionRequest(json.dumps({
    REQ_TYPE: REQ_TYPE_ACTION,
    REQ_ACTION_NAME: "link_down",
    REQ_INSTANCE_ID: "inst_0_link_down",
    REQ_ANOMALY_INSTANCE_ID: "inst_0_flap",
    REQ_ANOMALY_KEY: anomaly_key,
    REQ_CONTEXT: {"link_flap": action_data },
    REQ_TIMEOUT: 0 }))

print("down: dreq={}".format(str(dreq)))

dres = link_down_plugin.request(dreq)

print("safety: dres={}".format(str(dres)))

