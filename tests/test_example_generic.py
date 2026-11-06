# -*- coding: utf-8 -*-
"""
Runs an experiment with the simulation of the generic example, built with the tool-libs
version of :data:`pywisp.TOOL_LIBS_VERSION`, over both connections of the example.

Set ``TOOL_LIBS_SOURCE_DIR`` to a local tool-libs checkout to build against it instead of
fetching it, e.g. ``TOOL_LIBS_SOURCE_DIR=../tool-libs uv run pytest tests/test_example_generic.py``.
"""
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

import pywisp as pw
from pywisp.min import CONTROL_FRAME_ID, Control, controlFrame

EXAMPLE = Path(__file__).parents[1] / "examples" / "generic"

pytestmark = pytest.mark.skipif(shutil.which("cmake") is None or shutil.which("uv") is None,
                                reason="building the example needs cmake and uv")


def run(*cmd):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if res.returncode:
        pytest.fail(f"{' '.join(map(str, cmd))} failed:\n{res.stdout[-5000:]}")


@pytest.fixture(scope="session")
def simBinary(tmp_path_factory):
    """ the simulation, tool-libs is fetched in the version pywisp requires or taken from TOOL_LIBS_SOURCE_DIR """
    build = tmp_path_factory.mktemp("generic")
    local = os.environ.get("TOOL_LIBS_SOURCE_DIR")
    override = ["-D", f"FETCHCONTENT_SOURCE_DIR_TOOL-LIBS={Path(local).resolve()}"] if local else []
    run("cmake", "-S", EXAMPLE, "-B", build, "-D", "SIM=1", *override)
    run("cmake", "--build", build, "--target", "sim", "-j4")
    return build / "sim" / "sim"


@pytest.fixture
def sim(simBinary):
    # own session: without a controlling terminal the simulation does not log to it
    proc = subprocess.Popen([simBinary], cwd=simBinary.parent, start_new_session=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # wait until it listens on tcp, udp needs no connection
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", 45671), timeout=1).close()
            break
        except ConnectionRefusedError:
            time.sleep(0.05)
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
    pw.registerConnection(connection.Udp)
    pw.registerConnection(connection.Tcp)
    return testbench.DoublePendulum(), trajectory.Trajectory()


def test_tool_libs_version_is_used():
    deps = (EXAMPLE / "dependencies.cmake").read_text()
    assert "GIT_TAG ${TOOL_LIBS_VERSION}" in deps
    assert pw.TOOL_LIBS_VERSION


@pytest.mark.parametrize("connection", ["Udp", "Tcp"])
def test_generic_example(sim, example, qtbot, connection):
    from pywisp.connectionManager import ConnectionManager
    pendulum, traj = example
    manager = ConnectionManager()
    assert manager.setActiveConnection(connection)
    received = []
    manager.framesReceived.connect(received.extend)
    try:
        with qtbot.waitSignal(manager.stateChanged, timeout=5000,
                              check_params_cb=lambda state: state == manager.CONNECTED):
            manager.connect()
        # the rig sends status frames while idle
        qtbot.waitUntil(lambda: manager.isResponding() is True, timeout=5000)
        assert not manager.rigStatus[0].running

        # same settings as the default experiment of the example
        frames = pendulum.getParams([0]) + traj.getParams([1, [0, 1], [0, 0.15]])
        assert manager.expectStart(frames)
        # the rig stops the experiment after 1 s without heartbeat
        manager.startHeartbeat(250)
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
        assert data[-1]['DataPoints']['T'][0] == pytest.approx(0.15)

        model = [pendulum.handleFrame(f) for f in received if f.id == 15]
        assert model and model[-1]['DataPoints']['state'][0] != 0

        manager.write(controlFrame(Control.STOP))
        qtbot.waitUntil(lambda: not manager.rigStatus[0].running, timeout=5000)

        # without heartbeat, e.g. if pywisp crashed, the rig stops on its own and reports the missed heartbeat
        manager.stopHeartbeat()
        received.clear()
        manager.write(controlFrame(Control.START))
        qtbot.waitUntil(lambda: manager.rigStatus[0].running, timeout=5000)
        qtbot.waitUntil(lambda: not manager.rigStatus[0].running, timeout=5000)
        assert any(f.id == CONTROL_FRAME_ID for f in received)
    finally:
        manager.disconnect()
