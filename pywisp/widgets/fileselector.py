from PyQt5.QtWidgets import QFileDialog
import os
from .utils import settings

_default = {
    "path": [
        ("export_dir", os.path.curdir),
        ("export_ext", ".csv"),
    ]
}

class FileSelector(QFileDialog):
    def __init__(self, formats):
        super().__init__()
        self.st = settings(_default)
        self.formats = formats

    def getSaveFileName(self, text="Export as ..."):
        path = self.st.value("path/export_dir")
        ext = self.st.value("path/export_ext")
        file = os.path.join(path, "export" + ext)
        filterStr = ";;".join(self.formats)
        ix = [ ext in fmt for fmt in self.formats ].index(True)

        selection = super().getSaveFileName(self, text, file, filterStr, self.formats[ix])
        if not (filename := selection[0]):
            return
        selpath = os.path.dirname(filename)
        if path != selpath:
            self.st.setValue("path/export_dir", selpath)
        _, selext = os.path.splitext(filename)
        if ext != selext:
            self.st.setValue("path/export_ext", selext)

        return filename

