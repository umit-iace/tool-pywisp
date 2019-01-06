# -*- coding: utf-8 -*-
from collections import OrderedDict

import struct
from connection import ConnTestTCP
from pywisp.experimentModules import ExperimentModule


class ConstTrajectory(ExperimentModule):
    dataPoints = ['TrajHeaterOutput']

    publicSettings = OrderedDict([("Startwert", 0.0),
                                  ("Startzeit", 101.0),
                                  ("Endwert", 0.7)])

    connection = ConnTestTCP.__name__

    def __init__(self):
        ExperimentModule.__init__(self)

    def getStartParams(self):
        """
        Status byte with
        0 0 0 0 0 0 0 0
        7 6 5 4 3 2 1 0

        0 - manuel flag
        1 - const start flag
        Returns
        -------

        """
        payload = bytes([3])
        dataPoint = {'id': 44,
                     'msg': payload
                     }
        return dataPoint

    def getStopParams(self):
        payload = bytes([0])
        dataPoint = {'id': 44,
                     'msg': payload
                     }
        return dataPoint

    def getParams(self, data):
        payload = struct.pack('>fff',
                              data[0],
                              data[1] * 1000,
                              data[2])
        dataPoint = {'id': 45,
                     'msg': payload
                     }
        return dataPoint

    @staticmethod
    def handleFrame(frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == 46:
            data = struct.unpack('>Lf', frame.payload)
            dataPoints['Zeit'] = data[0]
            dataPoints['Punkte'] = {'TrajHeaterOutput': data[1]}
        else:
            dataPoints = None

        return dataPoints
