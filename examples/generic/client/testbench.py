# -*- coding: utf-8 -*-
from collections import OrderedDict

import struct
from connection import ConnTestTCP
from pywisp.experimentModules import ExperimentModule


class TwoPendulum(ExperimentModule):
    dataPoints = ['x',
                  'phi1',
                  'phi2',
                  'u',
                  ]

    publicSettings = OrderedDict()

    connection = ConnTestTCP.__name__

    def __init__(self):
        ExperimentModule.__init__(self)

    @staticmethod
    def handleFrame(self, frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == 10:
            data = struct.unpack('>Ldddd', frame.payload[:36])
            dataPoints['Time'] = data[0]
            dataPoints['DataPoints'] = {'x': data[1],
                                        'phi1': data[2],
                                        'phi2': data[3],
                                        'u': data[4],
                                        }
        else:
            dataPoints = None

        return dataPoints
