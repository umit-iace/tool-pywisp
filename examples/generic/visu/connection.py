# -*- coding: utf-8 -*-
from pywisp.connection import TcpConnection, UdpConnection


class Udp(UdpConnection):
    settings = {
        "ip": '127.0.0.1',
        "port": 45670,
    }

    def __init__(self):
        super().__init__(**self.settings)


class Tcp(TcpConnection):
    settings = {
        "ip": '127.0.0.1',
        "port": 45671,
    }

    def __init__(self):
        super().__init__(**self.settings)
