# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict
from pywisp.experimentModules import *
from pywisp.utils import packArrayToFrame, flatten

from connection import Connection


class Trajectory(ExperimentModule):
    dataPoints = [
        'T: y',
        'T: dy',
    ]
    publicSettings = OrderedDict([
        ("Type", 0),
        ("times", [0]),
        ("values", [0])
    ])

    connection = Connection.__name__

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
        fid = frame.min_id
        if fid == 25:
            data = struct.unpack(f'<L{len(Trajectory.dataPoints)}d', frame.payload)
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = dict(zip(Trajectory.dataPoints, data[1:]))
        else:
            dataPoints = None

        return dataPoints
