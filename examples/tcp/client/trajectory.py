# -*- coding: utf-8 -*-
from collections import OrderedDict

import struct
from connection import ConnTestTCP
from pywisp.experimentModules import ExperimentModule


class RampTrajectory(ExperimentModule):
    dataPoints = ['TrajOutput']

    publicSettings = OrderedDict([("Startwert", 0.0),
                                  ("Startzeit", 10),
                                  ("Endwert", 0.7),
                                  ("Endzeit", 15)])

    connection = ConnTestTCP.__name__

    def __init__(self):
        ExperimentModule.__init__(self)

    def getStartParams(self):
        pass

    def getStopParams(self):
        pass

    def getParams(self, data):
        payload = struct.pack('>dLdL',
                              data[0],
                              data[1],
                              data[2],
                              data[3])
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
            dataPoints['Zeit'] = data[0]
            dataPoints['Punkte'] = {'TrajOutput': data[1]}
        else:
            dataPoints = None

        return dataPoints
