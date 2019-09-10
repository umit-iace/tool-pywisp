# -*- coding: utf-8 -*-
from collections import OrderedDict

import struct
from connection import ConnTestTCP
from pywisp.experimentModules import ExperimentModule
from pywisp.utils import packArrayToFrame
import numpy as np
import logging


class RampTrajectory(ExperimentModule):
    dataPoints = ['TrajOutputRamp']

    publicSettings = OrderedDict([("StartValue", 0.0),
                                  ("StartTime", 10),
                                  ("EndValue", 0.7),
                                  ("EndTime", 15)])

    ids = [11, 13]

    connection = ConnTestTCP.__name__

    def __init__(self):
        ExperimentModule.__init__(self)

    def getStartParams(self):
        pass

    def getStopParams(self):
        pass

    def getParams(self, data):
        payload = struct.pack('>dLdL',
                              float(data[0]),
                              int(float(data[1]) * 1000),
                              float(data[2]),
                              int(float(data[3]) * 1000))
        dataPoint = {'id': self.ids[1],
                     'msg': payload
                     }
        return dataPoint

    def handleFrame(self, frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == self.ids[0]:
            data = struct.unpack('>Ld', frame.payload[:12])
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = {'TrajOutput': data[1]}
        else:
            dataPoints = None

        return dataPoints


class SeriesTrajectory(ExperimentModule):
    dataPoints = ['TrajOutputSeries']

    publicSettings = OrderedDict([("StartValue", 0.0),
                                  ("StartTime", 10),
                                  ("EndValue", 0.7),
                                  ("EndTime", 15)])

    ids = [15, 14]

    connection = ConnTestTCP.__name__

    oldData = None
    _logger = logging.getLogger(__name__)
    frameLength = 80

    def __init__(self):
        ExperimentModule.__init__(self)

    def getStartParams(self):
        pass

    def getStopParams(self):
        pass

    def getParams(self, data):
        if self.oldData != data:
            self._logger.info('Calc trajectory...')
            t = np.linspace(data[1], data[3], 101)
            trajData = []
            trajData.extend(t)
            dataPoint = None
            for _t in t:
                if _t <= data[1]:
                    trajData.append(data[0])
                elif _t >= data[3]:
                    trajData.append(data[2])
                else:
                    T = data[3] - data[1]
                    m = (data[2] - data[0]) / T
                    n = (data[0] * data[3] - data[2] * data[0]) / T
                    trajData.append(m * _t + n)

            self._logger.info('Send trajectory...')

            if dataPoint is None:
                dataPoint = packArrayToFrame(self.ids[1], np.array(trajData), self.frameLength, 4, 2)
            else:
                dataPoint += packArrayToFrame(self.ids[1], np.array(trajData), self.frameLength, 4, 2)

            return dataPoint

    def handleFrame(self, frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == self.ids[0]:
            data = struct.unpack('>Ld', frame.payload[:12])
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = {'TrajOutput': data[1]}
        else:
            dataPoints = None

        return dataPoints