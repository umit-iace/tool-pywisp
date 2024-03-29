# -*- coding: utf-8 -*-
from collections import OrderedDict
from pywisp.connection import *


class ConnTestTCP(UdpConnection):
    settings = OrderedDict([("ip", '127.0.0.1'),
                            ("port", '45670'),
                            ])

    def __init__(self):
        super().__init__(**self.settings)
