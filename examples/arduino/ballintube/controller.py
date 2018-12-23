# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict

from pywisp.experimentModules import ExperimentModule


class PIDController(ExperimentModule):
    dataPoints = []

    publicSettings = OrderedDict([("Kp", 12),
                                  ("Ti", 12),
                                  ("Td", 12)])

    def __init__(self):
        ExperimentModule.__init__(self)

    def getStartParams(self):
        """
        Status byte with
        0 0 0 0 0 0 0 0
        7 6 5 4 3 2 1 0

        0 - controller start flag
        Returns
        -------

        """
        payload = bytes([1])
        dataPoints = {'id': 50,
                      'msg': payload
                      }
        return dataPoints

    def getStopParams(self):
        payload = bytes([0])
        dataPoints = {'id': 50,
                      'msg': payload
                      }
        return dataPoints

    def getParams(self, data):
        payload = struct.pack('>fff',
                              data[0],
                              data[1],
                              data[2])
        dataPoints = {'id': 51,
                      'msg': payload
                      }
        return dataPoints

    @staticmethod
    def handleFrame(frame):
        dataPoints = None

        return dataPoints
