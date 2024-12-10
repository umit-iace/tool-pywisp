# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict

from pywisp.experimentModules import ExperimentModule

from connection import Connection


class DoublePendulum(ExperimentModule):
    dataPoints = [
        'pos',
        'phi1',
        'phi2',
        'u',
    ]

    publicSettings = OrderedDict([
        ("Config", 0),
    ])

    connection = Connection.__name__

    def getParams(self, data):
        payloadConfig = struct.pack('<B',
                                    int(data[0]),
                                    )

        dataPoints = [
            {'id': 10,
             'msg': payloadConfig
             },
        ]

        return dataPoints

    def handleFrame(self, frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == 15:
            data = struct.unpack(f'<L{len(DoublePendulum.dataPoints)}d', frame.payload)
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = dict(zip(DoublePendulum.dataPoints, data[1:]))
        else:
            dataPoints = None

        return dataPoints
