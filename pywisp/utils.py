# -*- coding: utf-8 -*-
import logging
import os

from PyQt5.QtGui import QColor
from pyqtgraph import mkPen


def get_resource(res_name, res_type="icons"):
    """
    Build absolute path to specified resource within the package
    Args:
        res_name (str): name of the resource
        res_type (str): subdir
    Return:
        str: path to resource
    """
    own_path = os.path.dirname(__file__)
    resource_path = os.path.abspath(os.path.join(own_path, "resources", res_type))
    return os.path.join(resource_path, res_name)


class PlainTextLogger(logging.Handler):
    """
    Logging handler hat formats log data for line display
    """

    def __init__(self, level=logging.NOTSET):
        logging.Handler.__init__(self, level)
        self.name = "PlainTextLogger"

        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S")
        self.setFormatter(formatter)

        self.cb = None

    def set_target_cb(self, cb):
        self.cb = cb

    def emit(self, record):
        msg = self.format(record)
        if self.cb:
            self.cb(msg)
        else:
            logging.getLogger().error("No callback configured!")


class DataPointBuffer(object):
    """
    Buffer object to store the values of the data points
    """

    def __init__(self, name):
        self.name = name
        self.values = []
        self.time = []

    def addValue(self, time, value):
        """
        Adds a new value to the data point buffer
        Args:
            time(float): time(stamp) of the corresponding value (x axis)
            value(float): the new value for the data point (y axis)
        """
        self.time.append(time)
        self.values.append(value)

    def clearBuffer(self):
        """
        Clears all the buffers of the data point
        """
        self.values.clear()
        self.time.clear()


class PlotChart(object):
    """
    Object containing the plot widgets and the associated plot curves
    """
    TABLEAU_COLORS = (
        ('blue', '#1f77b4'),
        ('orange', '#ff7f0e'),
        ('green', '#2ca02c'),
        ('red', '#d62728'),
        ('purple', '#9467bd'),
        ('brown', '#8c564b'),
        ('pink', '#e377c2'),
        ('gray', '#7f7f7f'),
        ('olive', '#bcbd22'),
        ('cyan', '#17becf'),
    )

    def __init__(self, title):
        self.title = title
        self.dataPoints = []
        self.plotWidget = None
        self.plotCurves = []

    def addPlotCurve(self, dataPoint):
        """
        Adds a curve to the plot widget
        Args:
            dataPoint(DataPointBuffer): Data point which contains the data be added
        """
        self.dataPoints.append(dataPoint)

        colorIdxItem = len(self.plotCurves) % len(self.TABLEAU_COLORS)
        colorItem = QColor(self.TABLEAU_COLORS[colorIdxItem][1])

        self.plotCurves.append(self.plotWidget.plot(name=dataPoint.name, pen=mkPen(colorItem, width=2)))

    def updatePlot(self):
        """
        Updates all curves of the plot with the actual data in the buffers
        """
        if self.plotWidget:
            for indx, curve in enumerate(self.plotCurves):
                curve.setData(self.dataPoints[indx].time, self.dataPoints[indx].values)

    def clear(self):
        if self.plotWidget:
            self.plotWidget.getPlotItem().clear()
            self.dataPoints = []
            self.plotCurves = []
