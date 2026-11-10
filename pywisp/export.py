# -*- coding: utf-8 -*-
"""
Export of data points to csv and png files.
"""
import logging
import os

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from .buffer import ElementBuffer
from .measurement import elementName
from .widgets.fileselector import FileSelector

__all__ = ["Exporter", "plotDataPoints"]


def expandDataPoints(dataPoints):
    """
    Replaces the array data points in `dataPoints` by their elements, named by
    :func:`pywisp.measurement.elementName`. An array data point whose element buffers are already
    given (e.g. the buffers of a measurement, with custom element names) is left out.

    :param dataPoints: dict of data point names and buffers
    :return: dict of names and buffers of numbers
    """
    given = {id(buf.parent) for buf in dataPoints.values() if isinstance(buf, ElementBuffer)}
    result = {}
    for name, buf in dataPoints.items():
        columns = getattr(buf, 'columns', None)
        if columns is None:
            result.setdefault(name, buf)
        elif id(buf) not in given:
            for idx in range(columns):
                result.setdefault(elementName(name, idx), buf.column(idx))
    return result


def plotDataPoints(dataPoints):
    """
    Plots the complete data points with matplotlib, starting at time 0.
    :param dataPoints: dict of data point names and buffers
    :return: matplotlib figure
    """
    # use the object oriented api, pyplot is not thread safe and
    # switching the global backend would break the gui
    fig = Figure(figsize=(10, 6))
    FigureCanvasAgg(fig)
    axes = fig.add_subplot(1, 1, 1)

    for name, buf in expandDataPoints(dataPoints).items():
        axes.plot(buf.time, buf.values, label=name)

    axes.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=4,
                ncol=4, mode="expand", borderaxespad=0., framealpha=0.5)
    axes.grid(True)
    axes.set_xlabel(r"Time (s)")
    axes.set_xlim(left=0)
    return fig


class Exporter(QObject):
    """
    Class exports data points from GUI to different formats (csv, png) as pandas dataframe.

    :param dataPoints: dict of data point names and buffers
    :param parameters: optional logged settings ``{'Module.setting': [(time, value), ...]}``, see
        :attr:`pywisp.measurement.Measurement.parameters`, exported as forward-filled csv columns before
        the data points, the png ignores them
    :param fileName: target file, asked for if not given
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

        self.worker = self.ExportThread(dataPoints, fileName, kwargs.get("parameters"))
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
        def __init__(self, data, file, parameters=None):
            super().__init__()
            self.dataPoints = data
            self.fileName = file
            self.parameters = parameters or {}
            self.df = None

        def run(self):
            # always report the end, otherwise the gui would wait for this export forever
            try:
                self._run()
            except Exception as e:
                self.info.emit(True, logging.ERROR, f"Export failed: {e!r}")

        def _run(self):
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
                 for key, val in expandDataPoints(self.dataPoints).items()}
            try:
                df = pd.DataFrame.from_dict(d, orient='index').transpose()
                df.sort_index(inplace=True)
                params = {}
                for key, values in self.parameters.items():
                    times, vals = zip(*values)
                    series = pd.Series(vals, index=times, dtype=object)
                    # of changes at the same time the last one is valid
                    series = series[~series.index.duplicated(keep='last')].sort_index()
                    params[key] = series.reindex(df.index, method='ffill')
                self.df = pd.concat([pd.DataFrame(params, index=df.index), df], axis=1)
                self.df.index.name = 'time'
            except Exception:
                self.df = None

        def exportPng(self):
            """
            Exports the data points as png with matplotlib.
            """
            plotDataPoints(self.dataPoints).savefig(self.fileName, dpi=300)

        def exportCsv(self, sep=','):
            """
            Exports the data point dataframe as csv
            :param sep: separator for csv (default: ,)
            """
            self.df.to_csv(self.fileName, sep=sep)
