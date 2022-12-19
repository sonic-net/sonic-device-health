# Python helper scripts per vendor
#

from swsscommon.swsscommon import SonicV2Connector

# globals
#
db = None
dbconn_cfg = None
dbconn_state = None

TABLE_NAME_ACTIONS = "LOM_ACTIONS"


def init_config() -> bool:
    try:
        db = SonicV2Connector(use_unix_socket_path=False)
        db.connect(CFG_DB)
        db.connect(STATE_DB)
        return True

    except Exception as e:
        log_error("Failed to connect to DB: ({})".format(str(e)))
        return False

def update_current_actions_config(name:str, config:{}):
    # Write into STATE-DB
    key = "{}:{}".format(TABLE_NAME_ACTIONS, name)
    try:
        for k, v in config.items():
            db.set(STATE_DB, key, k, v)
        return True

    except Exception as e:
        log_error("Failed to set entry to {}: ({})".format(key, str(e)))
        return False


def main():
    if not init_config():
        print("Failed to init")
        return

    if not update_actions_config("TEST", { "foo": "bar", "hello": "world" }):
        print("Failed to update")
        return

    print("Succeeded")


if __name__ == "__main__":
    msin()




