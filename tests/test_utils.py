import os
import pickle
import random
import string
import sys
import time
import unittest

import numpy as np

from PyQt5.QtWidgets import QApplication
from pywisp.utils import Exporter, DataPointBuffer

app = QApplication(sys.argv)
class ExporterTestCase(unittest.TestCase):
    base_path = os.path.dirname(__file__)
    d_name = os.path.join(base_path, "dataPoints.pkl")
    csv_name = os.path.join(base_path, "test.csv")
    png_name = os.path.join(base_path, "test.png")

    def setUp(self):
        if os.path.exists(self.d_name):
            # load test data
            with open(self.d_name, "rb") as f:
                self.dataPoints = pickle.load(f)
        else:
            # create test data
            lttrs = string.ascii_letters
            lbls = ["".join(random.choice(lttrs) for i in range(10))
                        for j in range(100)]
            self.dataPoints = {lbl: DataPointBuffer() for lbl in lbls}
            for t in range(0, 10000):
                for d in self.dataPoints.values():
                    d.addValue(t, random.random())
            with open(self.d_name, "wb") as f:
                pickle.dump(self.dataPoints, f)

        # remove conflicting files
        for f_name in [self.csv_name, self.png_name]:
            if os.path.exists(f_name):
                os.remove(f_name)

    def test_init(self):
        # normal init
        e = Exporter(dataPoints=self.dataPoints, fileName=self.csv_name)

    def test_export_csv(self):
        e = Exporter(dataPoints=self.dataPoints, fileName=self.csv_name)
        # this will spawn a new thread
        e.runExport()
        # wait until that is finished
        e.wait()
        del e
        self.assertTrue(os.path.exists(self.csv_name))

    def test_export_png(self):
        e = Exporter(dataPoints=self.dataPoints, fileName=self.png_name)
        # this will spawn a new thread
        e.runExport()
        # wait until that is finished
        e.wait()
        del e
        self.assertTrue(os.path.exists(self.png_name))

    def test_export_png_no_abort(self):
        e = Exporter(dataPoints=self.dataPoints, fileName=self.png_name)
        # this will spawn a new thread
        e.runExport()
        # do not wait (simulates closing the gui while exporting)
        del e
        # file should not be there as thread was killed
        self.assertFalse(os.path.exists(self.png_name))

    def test_timings(self):
        e = Exporter(dataPoints=self.dataPoints, fileName=self.csv_name)

        t0 = time.perf_counter()
        N = 10
        for n in range(N):
            e.worker._buildFrame()
        dt = time.perf_counter() - t0
        print(f"Average time needed for init is {dt/N} seconds.")

    def tearDown(self):
        for f_name in [self.csv_name, self.png_name]:
            if os.path.exists(f_name):
                os.remove(f_name)


if __name__ == '__main__':
    unittest.main()
