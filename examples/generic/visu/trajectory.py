# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict
from pywisp.experimentModules import *
from pywisp.utils import packArrayToFrame, flatten

import numpy as np


class Trajectory(ExperimentModule):
    dataPoints = [
        'T',
    ]
    dataPointElements = {'T': ['y', 'dy']}

    publicSettings = OrderedDict([
        ("Type", 0),
        ("times", [0]),
        ("values", [0])
    ])

    def __init__(self):
        ExperimentModule.__init__(self)

    def getParams(self, data):
        payloadConfig = struct.pack('<B',
                               int(data[0]),
                               )

        dataPoints = [
            {'id': 20, 'msg': payloadConfig},
            *packArrayToFrame(21, flatten(data[1:]), 80, 8, 4)
        ]

        return dataPoints

    def handleFrame(self, frame):
        dataPoints = {}
        fid = frame.id
        if fid == 25:
            # unpack_from: over Tcp the payload is padded to 80 bytes
            data = struct.unpack_from('<L2d', frame.payload)
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = {'T': np.array(data[1:3])}
        else:
            dataPoints = None

        return dataPoints
