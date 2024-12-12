from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QColor

import os

_default = {
    "log_colors": [
        ("CRITICAL", "#DC143C"),
        ("ERROR", "#B22222"),
        ("WARNING", "#DAA520"),
        ("INFO", "#101010"),
        ("DEBUG", "#4682B4"),
        ("NOTSET", "#000000"),
    ],
    "path": [
        ("export_dir", os.path.curdir),
        ("export_ext", ".csv"),
    ],
    "plot_colors": [
        ("blue", "#1f77b4"),
        ("orange", "#ff7f0e"),
        ("green", "#2ca02c"),
        ("red", "#d62728"),
        ("purple", "#9467bd"),
        ("brown", "#8c564b"),
        ("pink", "#e377c2"),
        ("gray", "#7f7f7f"),
        ("olive", "#bcbd22"),
        ("cyan", "#17becf"),
    ],
    "view": [
        ("show_coordinates", "True"),
    ],
}
class Settings(QSettings):
    def __init__(self):
        super().__init__()
        for group in _default.keys():
            self.beginGroup(group)
            keys = self.allKeys()
            for key, val in _default[group]:
                if key not in keys:
                    self.setValue(key, val)
            self.endGroup()

    def color(self, ix, kind='plot'):
        """ kind: one of ['plot', 'log'] """
        self.beginGroup(f'{kind}_colors')
        items = self.childKeys()
        key = ix if kind=='log' else items[ ix % len(items) ]
        ret = QColor(self.value(key))
        self.endGroup()
        return ret
