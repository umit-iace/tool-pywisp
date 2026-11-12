# -*- coding: utf-8 -*-
import pytest

import pywisp as pw


def test_register_and_lookup(cleanRegistry):
    class Conn(pw.UdpConnection):
        pass
    pw.registerConnection(Conn)
    assert pw.getRegisteredConnections() == {"Conn": Conn}


def test_register_twice(cleanRegistry):
    class Conn(pw.UdpConnection):
        pass
    pw.registerConnection(Conn)
    with pytest.raises(ValueError):
        pw.registerConnection(Conn)


def test_register_wrong_type(cleanRegistry):
    with pytest.raises(TypeError):
        pw.registerConnection(object)
