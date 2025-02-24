# -*- coding: utf-8 -*-
from pywisp import connection


class Connection(connection.UdpConnection):
    settings = {
        "ip": '127.0.0.1',
        "port": 45670,
    }

    def __init__(self):
        super().__init__(**self.settings)
