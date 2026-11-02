import time

import numpy as np
import pytest

from pywisp.buffer import DataPointBuffer
from pywisp.export import plotDataPoints
from pywisp.settings import Settings
import pywisp.widgets.plotchart as plotchart
from pywisp.widgets.plotchart import PlotChart

METHODS = ['peak', 'subsample', 'mean', 'off']


@pytest.fixture
def makeChart(qtbot):
    def make(**config):
        chart = PlotChart("test", config)
        qtbot.addWidget(chart)
        return chart
    return make


def signal(n, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n) * 0.01
    return t, np.sin(t) + rng.normal(0, 0.1, n)


def curveData(chart, name):
    x, y = chart.plotCurves[name].getData()
    return np.asarray(x), np.asarray(y)


def reference(method, ds, x, y):
    """ straight forward implementation of the downsampling methods """
    n = len(x) // ds
    if ds <= 1 or method == 'off':
        return x, y
    xs, ys = [], []
    for i in range(n):
        bx, by = x[i * ds:(i + 1) * ds], y[i * ds:(i + 1) * ds]
        if method == 'subsample':
            xs.append(bx[0])
            ys.append(by[0])
        elif method == 'mean':
            xs.append(bx[ds // 2])
            ys.append(by.mean())
        elif method == 'peak':
            xs += [bx[ds // 2]] * 2
            ys += [by.max(), by.min()]
    return np.array(xs), np.array(ys)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("ds", [1, 2, 7])
def test_downsample(makeChart, method, ds):
    chart = makeChart(downsamplingMethod=method)
    x, y = signal(1003)
    rx, ry = reference(method, ds, x, y)
    dx, dy = chart._downsample(ds, x, y)
    np.testing.assert_allclose(dx, rx)
    np.testing.assert_allclose(dy, ry)


def test_peak_keeps_extrema(makeChart):
    chart = makeChart(downsamplingMethod='peak')
    x, y = signal(1000)
    _, dy = chart._downsample(10, x, y)
    assert dy.max() == y.max()
    assert dy.min() == y.min()


@pytest.mark.parametrize("method", METHODS)
def test_cached_sample_matches_full_computation(makeChart, monkeypatch, method):
    """ adding data in chunks gives the same result as downsampling everything at once """
    chart = makeChart(downsamplingMethod=method)
    monkeypatch.setattr(chart, '_sampleStep', lambda x: 5)
    x, y = signal(1000)

    rng = np.random.default_rng(1)
    end = 0
    while end < len(x):
        end = min(len(x), end + int(rng.integers(1, 40)))
        cx, cy = chart._cachedSample('a', x[:end], y[:end])

        full = end // 5 * 5
        rx, ry = reference(method, 5, x[:full], y[:full])
        np.testing.assert_allclose(cx, np.concatenate((rx, x[full:end])))
        np.testing.assert_allclose(cy, np.concatenate((ry, y[full:end])))


def test_cached_sample_resets(makeChart, monkeypatch):
    chart = makeChart(downsamplingMethod='mean')
    x, y = signal(100)
    monkeypatch.setattr(chart, '_sampleStep', lambda x: 5)
    chart._cachedSample('a', x, y)

    # a different factor invalidates the cache
    monkeypatch.setattr(chart, '_sampleStep', lambda x: 10)
    cx, _ = chart._cachedSample('a', x, y)
    np.testing.assert_allclose(cx, reference('mean', 10, x, y)[0])

    # so does a buffer that got shorter, i.e. cleared
    cx, _ = chart._cachedSample('a', x[:30], y[:30])
    np.testing.assert_allclose(cx, reference('mean', 10, x[:30], y[:30])[0])


def test_update_curves_shows_all_data(makeChart, monkeypatch):
    chart = makeChart(MovingWindowEnable=False)
    monkeypatch.setattr(chart, '_sampleStep', lambda x: 1)
    buf = DataPointBuffer()
    chart.addCurve('a', buf)

    x, y = signal(500)
    for i in range(0, 500, 50):
        buf.extend(x[i:i + 50], y[i:i + 50])
        chart.updateCurves({'a': buf})
    cx, cy = curveData(chart, 'a')
    np.testing.assert_array_equal(cx, x)
    np.testing.assert_array_equal(cy, y)


def test_update_curves_moving_window(makeChart, monkeypatch):
    chart = makeChart(MovingWindowEnable=True, MovingWindowSize=2)
    monkeypatch.setattr(chart, '_sampleStep', lambda x: 1)
    x, y = signal(1000)
    a = DataPointBuffer(x, y)
    # a curve ending earlier is cut relative to the latest time stamp of all curves
    b = DataPointBuffer(x[:800], y[:800])
    chart.addCurve('a', a)
    chart.addCurve('b', b)
    chart.updateCurves({'a': a, 'b': b})

    ax, ay = curveData(chart, 'a')
    assert ax[0] >= x[-1] - 2 and ax[-1] == x[-1]
    np.testing.assert_array_equal(ay, y[x >= ax[0]])
    bx, _ = curveData(chart, 'b')
    assert bx[0] >= x[-1] - 2 and bx[-1] == x[799]


def test_update_curves_ignores_empty_and_unknown(makeChart):
    chart = makeChart()
    chart.addCurve('a', DataPointBuffer())
    chart.updateCurves({'a': DataPointBuffer(), 'unknown': DataPointBuffer([0.0], [1.0])})
    x, _ = chart.plotCurves['a'].getData()
    assert x is None or len(x) == 0


def test_curve_colors(makeChart):
    chart = makeChart()
    settings = Settings()
    for name in 'abc':
        chart.addCurve(name, DataPointBuffer([0.0], [0.0]))

    def colors():
        return [c.opts['pen'].color().name() for c in chart.plotCurves.values()]

    expected = [settings.color(i).name() for i in range(3)]
    assert colors() == expected

    # the remaining curves keep the color cycle without gaps
    chart.removeCurve('a')
    assert list(chart.plotCurves) == ['b', 'c']
    assert colors() == expected[:2]

    # removing an unknown curve is ignored
    chart.removeCurve('unknown')
    assert list(chart.plotCurves) == ['b', 'c']


def test_moving_window_width(makeChart, caplog):
    chart = makeChart(MovingWindowSize=5)
    chart.setMovingWindowWidth("12")
    assert chart.getMovingWindowWidth() == 12
    chart.setMovingWindowWidth("abc")
    assert chart.getMovingWindowWidth() == 12
    assert "Invalid moving window width" in caplog.text


@pytest.mark.parametrize("ext, magic", [('png', b'\x89PNG'), ('jpg', b'\xff\xd8'), ('pdf', b'%PDF')])
def test_chart_save_image(makeChart, tmp_path, monkeypatch, ext, magic):
    chart = makeChart(MovingWindowEnable=True, MovingWindowSize=1)
    buf = DataPointBuffer([0.5, 1.0, 5.0], [1.0, 2.0, 3.0])
    chart.addCurve('a', buf)
    chart.addCurve('empty', DataPointBuffer())

    # the image contains the complete data, not only the moving window
    plotted = {}
    def plot(dataPoints):
        plotted.update(dataPoints)
        return plotDataPoints(dataPoints)
    monkeypatch.setattr(plotchart, 'plotDataPoints', plot)

    fileName = tmp_path / f"chart.{ext}"
    chart.saveImage(str(fileName))
    assert fileName.read_bytes().startswith(magic)
    np.testing.assert_array_equal(plotted['a'].time, [0.5, 1.0, 5.0])


def test_plot_data_points_starts_at_zero():
    fig = plotDataPoints({'a': DataPointBuffer([2.0, 3.0], [1.0, 2.0])})
    assert fig.axes[0].get_xlim()[0] == 0


@pytest.mark.slow
@pytest.mark.parametrize("moving", [False, True])
@pytest.mark.parametrize("method", METHODS)
def test_incremental_update_timing(makeChart, qtbot, moving, method):
    """ benchmark of feeding a plot like during an experiment """
    chart = makeChart(MovingWindowEnable=moving, MovingWindowSize=30, downsamplingMethod=method)
    chart.show()
    x, y = signal(25000)
    bufs = {f"dp{i}": DataPointBuffer() for i in range(10)}
    for name, buf in bufs.items():
        chart.addCurve(name, buf)

    t0 = time.perf_counter()
    for i in range(0, len(x), 20):
        for buf in bufs.values():
            buf.extend(x[i:i + 20], y[i:i + 20])
        chart.updateCurves(bufs)
        qtbot.wait(0)
    dt = time.perf_counter() - t0
    print(f"\n{method=}, {moving=}: {dt / (len(x) / 20) * 1e3:.2f} ms per update")

    cx, _ = curveData(chart, 'dp0')
    assert cx[-1] == x[-1]
    if moving:
        assert cx[0] >= x[-1] - 30
