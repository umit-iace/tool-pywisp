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

    publicSettings = OrderedDict()

    connection = Connection.__name__

    def __init__(self):
        ExperimentModule.__init__(self)

    def handleFrame(self, frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == 10:
            data = struct.unpack(f'<L{len(DoublePendulum.dataPoints)}d', frame.payload)
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = dict(zip(DoublePendulum.dataPoints, data[1:]))
        else:
            dataPoints = None

        return dataPoints
