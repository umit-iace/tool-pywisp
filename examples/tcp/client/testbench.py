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

    publicSettings = OrderedDict([("Value1", 0.0),
                                  ("Value2", 10.0),
                                  ("Value3", 320),
                                  ("Value4", 10)])

    connection = ConnTestTCP.__name__

    def __init__(self):
        ExperimentModule.__init__(self)

    def getParams(self, data):
        payload = struct.pack('>dfhc',
                              data[0],
                              data[1],
                              data[2],
                              bytes(data[3]))
        dataPoint = {'id': 12,
                     'msg': payload
                     }
        return dataPoint

    @staticmethod
    def handleFrame(frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == 10:
            data = struct.unpack('>Ldfhc', frame.payload[:19])
            dataPoints['Zeit'] = data[0]
            dataPoints['Punkte'] = {'Value1': data[1],
                                    'Value2': data[2],
                                    'Value3': data[3],
                                    'Value4': data[4],
                                    }
        else:
            dataPoints = None

        return dataPoints
