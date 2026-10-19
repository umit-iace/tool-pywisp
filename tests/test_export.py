import gc
import time

import numpy as np
import pandas as pd
import pytest

from pywisp.buffer import DataPointBuffer
from pywisp.export import Exporter


@pytest.fixture
def dataPoints():
    """ two data points with different time bases """
    return {
        'a': DataPointBuffer([0.0, 1.0, 2.0], [1.0, 2.0, 3.0]),
        'b': DataPointBuffer([1.0, 3.0], [10.0, 30.0]),
    }


def runExport(qtbot, **kwargs):
    """ run an export and return its result """
    e = Exporter(**kwargs)
    with qtbot.waitSignal(e.done, timeout=60000) as blocker:
        e.runExport()
    e.wait()
    return blocker.args[0]


def test_export_csv(qtbot, tmp_path, dataPoints):
    fileName = tmp_path / "data.csv"
    assert runExport(qtbot, dataPoints=dataPoints, fileName=str(fileName))

    df = pd.read_csv(fileName, index_col='time')
    assert list(df.columns) == ['a', 'b']
    assert list(df.index) == [0.0, 1.0, 2.0, 3.0]
    np.testing.assert_array_equal(df['a'], [1.0, 2.0, 3.0, np.nan])
    np.testing.assert_array_equal(df['b'], [np.nan, 10.0, np.nan, 30.0])


def test_export_png(qtbot, tmp_path, dataPoints):
    fileName = tmp_path / "data.png"
    assert runExport(qtbot, dataPoints=dataPoints, fileName=str(fileName))
    assert fileName.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'


def test_export_unsupported_extension(qtbot, tmp_path, dataPoints):
    fileName = tmp_path / "data.txt"
    assert not runExport(qtbot, dataPoints=dataPoints, fileName=str(fileName))
    assert not fileName.exists()


def test_export_without_data(qtbot, tmp_path):
    fileName = tmp_path / "data.csv"
    assert not runExport(qtbot, dataPoints=None, fileName=str(fileName))
    assert not fileName.exists()


def test_export_survives_owner_deletion(qtbot, tmp_path):
    """ dropping the last reference to a running export must not destroy its thread """
    t = np.arange(200000) * 1e-3
    dataPoints = {f"dp{i}": DataPointBuffer(t, np.sin(t * i)) for i in range(20)}
    fileName = tmp_path / "export.csv"
    e = Exporter(dataPoints=dataPoints, fileName=str(fileName))
    e.runExport()
    del e
    gc.collect()
    qtbot.waitUntil(lambda: not Exporter._running, timeout=60000)
    assert fileName.exists()


@pytest.mark.slow
def test_build_frame_timing(tmp_path):
    rng = np.random.default_rng(0)
    t = np.arange(10000, dtype=float)
    dataPoints = {f"dp{i}": DataPointBuffer(t, rng.random(len(t))) for i in range(100)}
    e = Exporter(dataPoints=dataPoints, fileName=str(tmp_path / "data.csv"))

    N = 10
    t0 = time.perf_counter()
    for _ in range(N):
        e.worker._buildFrame()
    dt = time.perf_counter() - t0
    print(f"Building the data frame takes {dt / N * 1e3:.1f} ms.")
    assert e.worker.df.shape == (10000, 100)
