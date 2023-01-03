
"""
DROP
_lst_globals = { k:v for k, v in list(globals().items()) if k.startswith("test_") }

def _reset_all():
    for k in _lst_globals:
        globals()[k] = None
""" 


 TODO -- Vendors support

Vendor_subdir = "vendors"

class ActionType(Enum):
    ANOMALY = 0
    MITIGATION = 1
    SAFETYT_CHECK = 2


class ActionTypeStr(Enum):
    ANOMALY = "Anomaly"
    MITIGATION = "mitigation"
    SAFETYT_CHECK = "Safety-Check"

# *******************************
# Vendor related info
# *******************************
#
class vendorType(Enum):
    SONIC = "SONiC",
    CISCO = "Cisco",
    ARISTA = "Arista"
    UNKNOWN = "Unknown"


def get_vendor_type() -> vendorType:
    if os.path.exists("/etc/sonic"):
        return vendorType.SONIC
    return vendorType.UNKNOWN

def get_vendor_import_path():
    syspath.append(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        Vendor_subdir, get_vendor_type().value))


