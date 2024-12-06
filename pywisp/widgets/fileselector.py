from PyQt5.QtWidgets import QFileDialog
import logging
import os
import re
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
        self.exts = [self._extFromFilter(flt) for flt in formats]
        self.logger = logging.getLogger("FileSelector")

    def _extFromFilter(self, flt):
        return re.search(r'\*([.a-z]*)', flt).group(1)

    def getSaveFileName(self, text="Export as ..."):
        path = self.st.value("path/export_dir")
        ext = self.st.value("path/export_ext")
        file = os.path.join(path, "export")
        filterStr = ";;".join(self.formats)
        ix = [ ext in fmt for fmt in self.formats ].index(True)

        selpath, selfilt = super().getSaveFileName(self, text, file,
                                                   filterStr, self.formats[ix])
        if not selpath:
            self.logger.warn("File selection aborted!")
            return
        name, selext = os.path.splitext(selpath)
        if not selext:
            selext = self._extFromFilter(selfilt)
            selpath += selext
        elif selext not in selfilt:
            self.logger.error(f"Extension '{selext}' doesn't match used filter. Aborting!")
            return

        seldir = os.path.dirname(selpath)
        if path != selpath:
            self.st.setValue("path/export_dir", seldir)

        if ext != selext:
            self.st.setValue("path/export_ext", selext)

        return selpath

