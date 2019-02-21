# -*- coding: utf-8 -*-
from collections import OrderedDict

import struct
from connection import ConnTestTCP
from pywisp.experimentModules import ExperimentModule


class RampTrajectory(ExperimentModule):
    dataPoints = ['TrajOutput']

    publicSettings = OrderedDict([("StartValue", 0.0),
                                  ("StartTime", 10),
                                  ("EndValue", 0.7),
                                  ("EndTime", 15)])

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
        dataPoint = {'id': 13,
                     'msg': payload
                     }
        return dataPoint

    @staticmethod
    def handleFrame(frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == 11:
            data = struct.unpack('>Ld', frame.payload[:12])
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = {'TrajOutput': data[1]}
        else:
            dataPoints = None

        return dataPoints
