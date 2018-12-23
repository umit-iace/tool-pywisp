# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict

from pywisp.experimentModules import ExperimentModule


class ConstTrajectory(ExperimentModule):
    dataPoints = ['TrajAusgang']
    publicSettings = OrderedDict([("Startwert", 0.0),
                                  ("Startzeit", 101.0),
                                  ("Endwert", 0.7),
                                  ("PWM", True)])

    def __init__(self):
        ExperimentModule.__init__(self)

    def getStartParams(self):
        """
        Status byte with
        0 0 0 0 0 0 0 0
        7 6 5 4 3 2 1 0

        0 - manuel flag
        1 - const start flag
        2 - sinoid start flag
        Returns
        -------

        """
        payload = bytes([3])
        dataPoints = {'id': 40,
                      'msg': payload
                      }
        return dataPoints

    def getStopParams(self):
        payload = bytes([0])
        dataPoints = {'id': 40,
                      'msg': payload
                      }
        return dataPoints

    def getParams(self, data):
        payload = struct.pack('>fffh',
                              data[0],
                              data[1] * 1000,
                              data[2],
                              int(bool(data[3])))
        dataPoints = {'id': 41,
                      'msg': payload
                      }
        return dataPoints

    @staticmethod
    def handleFrame(frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == 43:
            data = struct.unpack('>Lf', frame.payload)
            dataPoints['Zeit'] = data[0]
            dataPoints['Punkte'] = {'TrajAusgang': data[1]}
        else:
            dataPoints = None

        return dataPoints


class SinoidTrajectory(ExperimentModule):
    dataPoints = ['TrajAusgang']
    publicSettings = OrderedDict([("Amplitude", 0.2),
                                  ("Frequenz", 1),
                                  ("Amplitude0", 0.7),
                                  ("Startwert", 0),
                                  ("Startzeit", 5),
                                  ("PWM", True)])

    def __init__(self):
        ExperimentModule.__init__(self)

    def getStartParams(self):
        """
        Status byte with
        0 0 0 0 0 0 0 0
        7 6 5 4 3 2 1 0

        0 - manuel flag
        1 - const start flag
        2 - sinoid start flag
        Returns
        -------

        """
        payload = bytes([5])
        dataPoints = {'id': 40,
                      'msg': payload
                      }
        return dataPoints

    def getStopParams(self):
        payload = bytes([0])
        dataPoints = {'id': 40,
                      'msg': payload
                      }
        return dataPoints

    def getParams(self, data):
        payload = struct.pack('>fffffh',
                              data[0],
                              data[1],
                              data[2],
                              data[3],
                              data[4] * 1000,
                              int(bool(data[5])))
        dataPoints = {'id': 42,
                      'msg': payload
                      }
        return dataPoints

    @staticmethod
    def handleFrame(frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == 43:
            data = struct.unpack('>Lf', frame.payload)
            dataPoints['Zeit'] = data[0]
            dataPoints['Punkte'] = {'TrajAusgang': data[1]}
        else:
            dataPoints = None

        return dataPoints
