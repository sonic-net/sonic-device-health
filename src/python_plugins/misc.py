
"""
DROP
_lst_globals = { k:v for k, v in list(globals().items()) if k.startswith("test_") }

def _reset_all():
    for k in _lst_globals:
        globals()[k] = None
""" 
