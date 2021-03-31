# -*- coding: utf-8 -*-
from collections import OrderedDict

from pywisp.connection import TcpConnection


class ConnTestTCP(TcpConnection):
    settings = OrderedDict([("ip", '127.0.0.1'),
                            ("port", '50007'),
                            ])

    def __init__(self):
        TcpConnection.__init__(self,
                               self.settings['ip'],
                               self.settings['port'])
