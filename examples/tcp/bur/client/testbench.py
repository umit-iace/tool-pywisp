# -*- coding: utf-8 -*-
from collections import OrderedDict

import struct
from connection import ConnTestTCP

from pywisp.experimentModules import ExperimentModule


class Test(ExperimentModule):
    dataPoints = ['Value1',
                  'Value2',
                  'Value3',
                  'Value4',
                  'ValueNan',
                  'ValueInf'
                  ]

    publicSettings = OrderedDict([("Value1", 0.0),
                                  ("Value2", 10.0),
                                  ("Value3", 320),
                                  ("Value4", 10)])

    ids = [10, 12]

    connection = ConnTestTCP.__name__

    def __init__(self):
        ExperimentModule.__init__(self)

    def getParams(self, data):
        payload = struct.pack('>dfhB',
                              float(data[0]),
                              float(data[1]),
                              int(data[2]),
                              int(data[3]) % 256)
        dataPoint = {'id': self.ids[1],
                     'msg': payload
                     }
        return dataPoint

    def handleFrame(self, frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == self.ids[0]:
            data = struct.unpack('<Ldfhb2d', frame.payload[:35])
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = {'Value1': data[1],
                                        'Value2': data[2],
                                        'Value3': data[3],
                                        'Value4': data[4],
                                        'ValueNan': data[5],
                                        'ValueInf': data[6],
                                        }
        else:
            dataPoints = None

        return dataPoints