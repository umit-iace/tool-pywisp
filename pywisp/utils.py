# -*- coding: utf-8 -*-
import logging
import numpy as np
import os
from PyQt5.QtGui import QColor
from pyqtgraph import mkPen

from pywisp import TABLEAU_COLORS


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

        colorIdxItem = len(self.plotCurves) % len(TABLEAU_COLORS)
        colorItem = QColor(TABLEAU_COLORS[colorIdxItem][1])

        self.plotCurves.append(self.plotWidget.plot(name=dataPoint.name, pen=mkPen(colorItem, width=2)))

    def updatePlot(self):
        """
        Updates all curves of the plot with the actual data in the buffers
        """
        if self.plotWidget:
            for indx, curve in enumerate(self.plotCurves):
                datax = self.dataPoints[indx].time
                datay = self.dataPoints[indx].values
                if datax:
                    interpx = np.linspace(datax[0], datax[-1], 100)
                    # TODO _currentInterpolationPoints
                    interpy = np.interp(interpx, datax, datay)
                    curve.setData(interpx, interpy)

    def clear(self):
        if self.plotWidget:
            self.plotWidget.getPlotItem().clear()
            self.dataPoints = []
            self.plotCurves = []


class CSVExporter(object):
    def __init__(self, chart):
        self.chart = chart
        self.sep = ','

    def export(self, fileName):

        if not isinstance(self.chart, PlotChart):
            raise Exception("Must have a chart selected for CSV export.")

        fd = open(fileName, 'w')
        data = []
        header = []

        for dataPoint in self.chart.dataPoints:
            if dataPoint.time:
                header.append('Zeit')
                header.append(dataPoint.name)
                data.append(dataPoint.time)
                data.append(dataPoint.values)

        numColumns = len(header)
        if data:
            numRows = len(max(data, key=len))
        else:
            fd.close()
            return

        fd.write(self.sep.join(header) + '\n')

        for i in range(numRows):
            for j in range(numColumns):
                if i < len(data[j]):
                    fd.write(str(data[j][i]))
                else:
                    fd.write(str(np.nan))

                if j < numColumns:
                    fd.write(self.sep)

            fd.write('\n')
        fd.close()
