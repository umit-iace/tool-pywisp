# -*- coding: utf-8 -*-
"""
Export of data points to csv and png files.
"""
import logging
import os

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from .widgets.fileselector import FileSelector

__all__ = ["Exporter"]


class Exporter(QObject):
    """
    Class exports data points from GUI to different formats (csv, png) as pandas dataframe.
    """
    done = pyqtSignal(bool)
    # running exports keep themselves alive, destroying a running QThread aborts the process
    _running = set()

    def __init__(self, **kwargs):
        super().__init__()
        dataPoints = kwargs.get("dataPoints", None)
        fileName = kwargs.get("fileName", None) or FileSelector(
            ["CSV Data (*.csv)", "PNG Image (*.png)"]
        ).getSaveFileName()

        self.worker = self.ExportThread(dataPoints, fileName)
        self.logger = logging.getLogger("Exporter")
        def handleLog(done, lvl, msg):
            self.logger.log(lvl, msg)
            if done:
                self.done.emit(lvl != logging.ERROR)
        self.worker.info.connect(handleLog)

    def runExport(self):
        Exporter._running.add(self)
        # queued to the gui thread, since the exporter lives there
        self.worker.finished.connect(self._onFinished)
        self.worker.start()

    def _onFinished(self):
        Exporter._running.discard(self)

    def wait(self):
        try:
            self.worker.wait()
        except RuntimeError: # happens when ExportThread already cleaned up on C++ side
            pass

    class ExportThread(QThread):
        info = pyqtSignal(bool,int,str)
        def __init__(self, data, file):
            super().__init__()
            self.dataPoints = data
            self.fileName = file
            self.df = None

        def run(self):
            if self.dataPoints is None:
                self.info.emit(True, logging.ERROR, "Export failed: No data given")
                return
            if self.fileName is None:
                self.info.emit(True, logging.ERROR, "Export failed: No file name given")
                return
            self.info.emit(False, logging.INFO, f"Export to {self.fileName} started.")
            self._buildFrame()
            if self.df is None:
                self.info.emit(True, logging.ERROR, "Export failed: Cannot build data frame")
                return
            file, ext = os.path.splitext(self.fileName)
            if ext == '.csv':
                self.exportCsv()
            elif ext == '.png':
                self.exportPng()
            else:
                self.info.emit(True, logging.ERROR, f"Export failed: Unsupported file extension '{ext}'.")
                return
            self.info.emit(True, logging.INFO, "Export successful.")

        def _buildFrame(self):
            # build pandas data frame
            d = {key: pd.Series(val.values, index=val.time)
                 for key, val in self.dataPoints.items()}
            try:
                self.df = pd.DataFrame.from_dict(d, orient='index').transpose()
                self.df.index.name = 'time'
                self.df.sort_index(inplace=True)
            except Exception:
                self.df = None

        def exportPng(self):
            """
            Exports the data point dataframe as png with matplotlib.
            :param fileName: name of file with extension
            """

            # use the object oriented api, pyplot is not thread safe and
            # switching the global backend would break the gui
            fig = Figure(figsize=(10, 6))
            FigureCanvasAgg(fig)
            axes = fig.add_subplot(1, 1, 1)

            for col in self.df.columns:
                series = self.df[col].dropna()
                axes.plot(series.index, series.values, label=col)

            axes.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=4,
                        ncol=4, mode="expand", borderaxespad=0., framealpha=0.5)

            axes.grid(True)
            if self.df.index.name == 'time':
                axes.set_xlabel(r"Time (s)")

            fig.savefig(self.fileName, dpi=300)

        def exportCsv(self, sep=','):
            """
            Exports the data point dataframe as csv
            :param sep: separator for csv (default: ,)
            """
            self.df.to_csv(self.fileName, sep=sep)
