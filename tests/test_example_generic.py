# -*- coding: utf-8 -*-
"""
Runs an experiment with the simulation of the generic example, built with the tool-libs
version of :data:`pywisp.TOOL_LIBS_VERSION`.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

import pywisp as pw
from pywisp.min import Control, controlFrame

EXAMPLE = Path(__file__).parents[1] / "examples" / "generic"

pytestmark = pytest.mark.skipif(shutil.which("cmake") is None or shutil.which("uv") is None,
                                reason="building the example needs cmake and uv")


def run(*cmd):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if res.returncode:
        pytest.fail(f"{' '.join(map(str, cmd))} failed:\n{res.stdout[-5000:]}")


@pytest.fixture(scope="session")
def simBinary(tmp_path_factory):
    """ the simulation, tool-libs is fetched in the version pywisp requires """
    build = tmp_path_factory.mktemp("generic")
    run("cmake", "-S", EXAMPLE, "-B", build, "-D", "SIM=1")
    run("cmake", "--build", build, "--target", "sim", "-j4")
    return build / "sim" / "sim"


@pytest.fixture
def sim(simBinary):
    # own session: without a controlling terminal the simulation does not log to it
    proc = subprocess.Popen([simBinary], cwd=simBinary.parent, start_new_session=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    yield proc
    proc.kill()
    proc.wait()


@pytest.fixture
def example(monkeypatch, cleanRegistry):
    """ the experiment modules of the example """
    monkeypatch.syspath_prepend(str(EXAMPLE / "visu"))
    import connection
    import testbench
    import trajectory
    pw.registerConnection(connection.Connection)
    return testbench.DoublePendulum(), trajectory.Trajectory()


def test_tool_libs_version_is_used():
    deps = (EXAMPLE / "dependencies.cmake").read_text()
    assert "GIT_TAG ${TOOL_LIBS_VERSION}" in deps
    assert pw.TOOL_LIBS_VERSION


def test_generic_example(sim, example, qtbot):
    from pywisp.connectionManager import ConnectionManager
    pendulum, traj = example
    name = "Connection"
    manager = ConnectionManager()
    received = []
    manager.framesReceived.connect(lambda frames, _: received.extend(frames))
    try:
        with qtbot.waitSignal(manager.stateChanged, timeout=5000,
                              check_params_cb=lambda state: state == manager.CONNECTED):
            manager.connectAll()
        # the rig sends status frames while idle
        qtbot.waitUntil(lambda: manager.isResponding(name) is True, timeout=5000)
        assert not manager.rigStatus[name][0].running

        # same settings as the default experiment of the example
        frames = [dict(f, connection=name)
                  for f in pendulum.getParams([0]) + traj.getParams([1, [0, 1], [0, 0.15]])]
        assert manager.expectStart({name: frames})
        with qtbot.waitSignal(manager.startConfirmed, timeout=5000):
            with qtbot.assertNotEmitted(manager.startFailed, wait=0):
                for f in frames:
                    manager.write(f)
                manager.write(controlFrame(Control.START))

        def trajData():
            return [traj.handleFrame(f) for f in received if f.id == 25]
        # the trajectory reaches its end value after 1 s
        qtbot.waitUntil(lambda: bool(trajData()) and trajData()[-1]["Time"] > 1200, timeout=10000)
        data = trajData()
        times = [d['Time'] for d in data]
        assert times == sorted(times)
        assert data[-1]['DataPoints']['T: y'] == pytest.approx(0.15)

        model = [pendulum.handleFrame(f) for f in received if f.id == 15]
        assert model and model[-1]['DataPoints']['pos'] != 0

        manager.write(controlFrame(Control.STOP))
        qtbot.waitUntil(lambda: not manager.rigStatus[name][0].running, timeout=5000)
    finally:
        manager.disconnectAll()
