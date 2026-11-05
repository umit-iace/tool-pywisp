# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict

import numpy as np

from pywisp.experimentModules import ExperimentModule

from connection import Connection


class DoublePendulum(ExperimentModule):
    dataPoints = [
        'state',
        'u',
    ]
    dataPointElements = {'state': ['pos', 'phi1', 'phi2']}

    publicSettings = OrderedDict([
        ("Config", 0),
    ])

    connection = Connection.__name__

    def getParams(self, data) -> list[dict]:
        payloadConfig = struct.pack('<B',
                                    int(data[0]),
                                    )

        dataPoints = [
            {'id': 10,
             'msg': payloadConfig
             },
        ]

        return dataPoints

    def handleFrame(self, frame) -> dict:
        dataPoints = {}
        fid = frame.id
        if fid == 15:
            data = struct.unpack('<L4d', frame.payload)
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = {'state': np.array(data[1:4]), 'u': data[4]}
        else:
            dataPoints = None

        return dataPoints
