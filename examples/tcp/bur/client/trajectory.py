# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict

import numpy as np

from pywisp.experimentModules import ExperimentModule
from pywisp.utils import packArrayToFrame


class RampTrajectory(ExperimentModule):
    dataPoints = ['TrajOutputRamp']

    publicSettings = OrderedDict([("StartValue", 0.0),
                                  ("StartTime", 10),
                                  ("EndValue", 0.7),
                                  ("EndTime", 15)])

    def getParams(self, data):
        payload = struct.pack('<dLdL',
                              float(data[0]),
                              int(data[1] * 1000),
                              float(data[2]),
                              int(data[3] * 1000))
        return [{'id': 13, 'msg': payload}]

    def handleFrame(self, frame):
        if frame.id != 11:
            return None
        data = struct.unpack_from('<Ld', frame.payload)
        return {'Time': data[0], 'DataPoints': {'TrajOutputRamp': data[1]}}


class SeriesTrajectory(ExperimentModule):
    dataPoints = ['TrajOutputSeries']

    publicSettings = OrderedDict([("StartValue", 0.0),
                                  ("StartTime", 10),
                                  ("EndValue", 0.7),
                                  ("EndTime", 15)])

    # the plc stores at most 256 values, i.e. 128 points
    points = 101

    def getParams(self, data):
        startValue, startTime, endValue, endTime = data
        # ramp as series of points, the plc interpolates linearly between them
        t = np.linspace(startTime * 1000, endTime * 1000, self.points)
        values = np.linspace(startValue, endValue, self.points)
        # all times [ms], then all values, the first frame starts with the number of values
        return packArrayToFrame(14, np.concatenate([t, values]), 80, 8, 2)

    def handleFrame(self, frame):
        if frame.id != 15:
            return None
        data = struct.unpack_from('<Ld', frame.payload)
        return {'Time': data[0], 'DataPoints': {'TrajOutputSeries': data[1]}}
