# -*- coding: utf-8 -*-
from pywisp.connection import UdpConnection


class Connection(UdpConnection):
    settings = {
        "ip": '127.0.0.1',
        "port": 45670,
    }

    def __init__(self):
        super().__init__(**self.settings)
