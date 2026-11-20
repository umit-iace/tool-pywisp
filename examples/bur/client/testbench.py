# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict

from pywisp.experimentModules import ExperimentModule


class Test(ExperimentModule):
    dataPoints = ['Value1',
                  'Value2',
                  'Value3',
                  'Value4',
                  'ValueNan',
                  'ValueInf',
                  ]

    publicSettings = OrderedDict([("Value1", 0.0),
                                  ("Value2", 10.0),
                                  ("Value3", 320),
                                  ("Value4", 10)])

    def getParams(self, data):
        payload = struct.pack('<dfhB',
                              float(data[0]),
                              float(data[1]),
                              int(data[2]),
                              int(data[3]) % 256)
        return [{'id': 12, 'msg': payload}]

    def handleFrame(self, frame):
        if frame.id != 10:
            return None
        # unpack_from: the payload is padded to 80 bytes
        data = struct.unpack_from('<LdfhB2d', frame.payload)
        return {'Time': data[0],
                'DataPoints': dict(zip(self.dataPoints, data[1:])),
                }
