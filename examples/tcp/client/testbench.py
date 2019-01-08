# -*- coding: utf-8 -*-
from collections import OrderedDict

import struct
from connection import ConnTestTCP
from pywisp.experimentModules import ExperimentModule


class TestTCP(ExperimentModule):
    dataPoints = ['Value1',
                  'Value2',
                  'Value3',
                  'Value4',
                  ]

    publicSettings = OrderedDict()

    connection = ConnTestTCP.__name__

    def __init__(self):
        ExperimentModule.__init__(self)

    def getParams(self, data):
        """
        Status byte with
        0 0 0 0 0 0 0 0
        7 6 5 4 3 2 1 0

        0 - analog read of AirFlowMeter dv meter
        Returns
        -------

        """
        payload = struct.pack('h',
                              int(bool(1)))
        dataPoint = {'id': 14,
                     'msg': payload
                     }
        return dataPoint

    @staticmethod
    def handleFrame(frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == 10:
            data = struct.unpack('>Lffff', frame.payload)
            dataPoints['Zeit'] = data[0]
            dataPoints['Punkte'] = {'Value1': data[1],
                                    'Value2': data[2],
                                    'Value3': data[3],
                                    'Value4': data[4],
                                    }
        else:
            dataPoints = None

        return dataPoints
