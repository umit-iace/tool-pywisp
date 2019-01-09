# -*- coding: utf-8 -*-
from collections import OrderedDict

from pywisp.connection import SerialConnection


class ConnTestSerial(SerialConnection):
    settings = OrderedDict([("port", '/dev/uart0'),
                            ("baud", 115200),
                            ])

    def __init__(self):
        SerialConnection.__init__(self,
                                  self.settings['port'],
                                  self.settings['baud'])
