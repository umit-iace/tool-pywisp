
from PyQt5.QtCore import QSettings

def settings(default: None):
    """ default= {
    group1: [
            (key1, val1),
            (key2, val2),
            ...
            ],
        ...
        }
    """
    st = QSettings()
    if not default:
        return st
    for group in default.keys():
        st.beginGroup(group)
        keys = st.allKeys()
        for key, val in default[group]:
            if key not in keys:
                st.setValue(key, val)
        st.endGroup()
    return st
