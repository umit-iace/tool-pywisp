# -*- coding: utf-8 -*-
from collections import OrderedDict

import struct
from connection import ConnTestTCP
from pywisp.experimentModules import ExperimentModule


class TestTCP(ExperimentModule):
    dataPoints = ['Wert1',
                  'Wert2',
                  'Wert3',
                  'Wert4',
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
                              int(bool(data[0])))
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
            dataPoints['Punkte'] = {'Wert1': data[1],
                                    'Wert2': data[2],
                                    'Wert3': data[3],
                                    'Wert4': data[4],
                                    }
        else:
            dataPoints = None

        return dataPoints
