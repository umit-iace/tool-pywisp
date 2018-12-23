# -*- coding: utf-8 -*-
import sys
from collections import OrderedDict

import os
import struct

sys.path.insert(0, os.path.dirname(os.path.realpath('__file__')) + '/../../../Identifikation/')
import settingsV3 as st
from pywisp.experimentModules import ExperimentModule


class BallInTube(ExperimentModule):
    dataPoints = ['Drehzahl', 'Position', 'Spannung', 'PWM']
    publicSettings = OrderedDict([("ASp", st.ASp),
                                  ("kV", st.kV),
                                  ("kL", st.kL),
                                  ("Ks", st.Ks),
                                  ("mass", st.m),
                                  ("n0", st.n0)])

    def __init__(self):
        ExperimentModule.__init__(self)

    def getParams(self, data):
        payload = struct.pack('>ffffff',
                              data[0],
                              data[1],
                              data[2],
                              data[3],
                              data[4],
                              data[5])
        dataPoints = {'id': 30,
                      'msg': payload
                      }

        return dataPoints

    @staticmethod
    def handleFrame(frame):
        dataPoints = {}
        fid = frame.min_id
        if fid == 10:
            data = struct.unpack('>Lffff', frame.payload)
            dataPoints['Zeit'] = data[0]
            dataPoints['Punkte'] = {'Drehzahl': data[1],
                                    'Position': data[2],
                                    'Spannung': data[3],
                                    'PWM': data[4]
                                    }
        else:
            dataPoints = None

        return dataPoints
