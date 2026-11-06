# -*- coding: utf-8 -*-
from pywisp.connection import TcpConnection


class ConnTestTCP(TcpConnection):
    # 127.0.0.1 for ARsim on this pc, otherwise the ip of the plc
    settings = {
        "ip": '127.0.0.1',
        "port": 50007,
    }

    def __init__(self):
        super().__init__(**self.settings)
