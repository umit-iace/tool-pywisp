# -*- coding: utf-8 -*-
from collections import OrderedDict

import struct
from connection import ConnTestSerial
from pywisp.experimentModules import ExperimentModule


class RampTrajectory(ExperimentModule):
    dataPoints = ['TrajOutput']

    publicSettings = OrderedDict([("StartValue", 0.0),
                                  ("StartTime", 10),
                                  ("EndValue", 0.7),
                                  ("EndTime", 15)])

    ids = [11, 13]

    connection = ConnTestSerial.__name__

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
            data = struct.unpack('>Ld', frame.payload)
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = {'TrajOutput': data[1]}
        else:
            dataPoints = None

        return dataPoints
