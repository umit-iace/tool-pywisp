# -*- coding: utf-8 -*-
import unittest

from PyQt5.QtWidgets import QApplication


class SerialTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def test_valid_baudrate(self):
        import pywisp as pw
        # clear the registry the hard way
        pw.registry._registry = pw.registry.Registry()
        class GoodConnection(pw.SerialConnection):
            settings = {
                "port": 'ttyIDK',
                "baud": 1000000, 
            }
            def __init__(self):
                super().__init__(**self.settings)
        pw.registerConnection(GoodConnection)
        app = QApplication([])
        form = pw.MainGui()
        form.connect()

    def test_invalid_baudrate(self):
        import pywisp as pw
        # clear the registry the hard way
        pw.registry._registry = pw.registry.Registry()
        class BadConnection(pw.SerialConnection):
            settings = {
                "port": 'ttyIDK',
                "baud": 123456, 
            }

            def __init__(self):
                super().__init__(**self.settings)
        pw.registerConnection(BadConnection)
        app = QApplication([])
        form = pw.MainGui()
        with self.assertRaises(ValueError):
            form.connect()


