"""
Builds the B&R server (``../server/br_server.apj``), starts it in ARsim (or transfers it to a PLC) and runs a TCP
integration test against it: status frame, start/sync/stop, sync before start, data frames, heartbeat, reconnect.
Talks raw TCP (81-byte chunks: 1 id + 80 payload) with pywisp.min for the control/status frames, no GUI.

Build and ARsim need Windows with Automation Studio 4.4 (BR.AS.Build.exe) and PVI (PVITransfer.exe),
the test alone runs anywhere (``--test-only``). From the repository root:

    uv run python examples/tcp/bur/test/arsim_test.py                        # build, ARsim, test, stop ARsim
    uv run python examples/tcp/bur/test/arsim_test.py --skip-build --keep-running
    uv run python examples/tcp/bur/test/arsim_test.py --target-ip 10.0.0.2  # build for and install on the PLC
    uv run python examples/tcp/bur/test/arsim_test.py --test-only --host 10.0.0.2

Exit code = number of failed tests, 1 if build, transfer or start failed.
"""
import argparse
import os
import queue
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from pywisp.min import (CONTROL_FRAME_ID, STATUS_FRAME_ID, Control, RigStatus,
                        controlFrame, frameCrc, syncFrame)

PROJECT_DIR = Path(__file__).resolve().parent.parent / 'server'
APJ = PROJECT_DIR / 'br_server.apj'

PAYLOAD = 80
CHUNK = PAYLOAD + 1
HEARTBEAT_PERIOD = 0.1  # s, below the 1 s HEARTBEAT_TIMEOUT of TcpIpServer
# frame ids the server sends, anything else means the 81-byte stream is misaligned
SERVER_IDS = {CONTROL_FRAME_ID, STATUS_FRAME_ID, 10, 11, 15}
CYCLE_MS = 100  # Cyclic#4, benchData.lTime step


# ---------------------------------------------------------------- build and ARsim

BR_ROOT = Path(r'C:\BrAutomation')


def findTool(path, pattern, prefer, option):
    """ the given path, else the match of pattern below C:\\BrAutomation, the one containing prefer if several """
    if path:
        if not Path(path).is_file():
            raise RuntimeError(f"{path} not found, check {option}")
        return path
    found = sorted(BR_ROOT.glob(pattern))
    if not found:
        raise RuntimeError(f"no {pattern} below {BR_ROOT}, pass {option} <path to the exe>")
    tool = next((f for f in found if prefer in str(f)), found[-1])
    print(f"   {tool.name}: {tool}" + (f" (of {len(found)}, choose with {option})" if len(found) > 1 else ""))
    return str(tool)


def stopArsim(arsimDir):
    """ ARsim runs as ar000loader.exe / AR000.exe, only one instance can use the port; a PVITransfer left over from an
    aborted run can keep files of the ARsim directory open """
    for exe in ('ar000loader.exe', 'AR000.exe', 'PVITransfer.exe'):
        subprocess.run(['taskkill', '/F', '/T', '/IM', exe], capture_output=True)
    time.sleep(1)  # taskkill returns before the processes released their files


def removeDir(path):
    for _ in range(10):
        try:
            subprocess.run(['cmd', '/c', 'rmdir', '/s', '/q', str(path)], capture_output=True)
            if not path.exists():
                return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError(f"cannot remove {path}")


def build(args, onPlc):
    cmd = [args.as_build, str(APJ), '-c', args.configuration, '-buildMode', 'Rebuild', '-buildRUCPackage']
    if not onPlc:
        cmd.append('-simulation')
    print(f"== Build {APJ.name} ({args.configuration}) {'for the PLC' if onPlc else 'for simulation'}", flush=True)
    code = subprocess.run(cmd).returncode
    # 0 = ok, 1 = warnings, 3 = errors
    if code > 1:
        raise RuntimeError(f"build failed with exit code {code}")


def findRuc(args):
    # simulation and PLC builds write the same file: with --skip-build it must come from the right kind of build
    rucs = sorted((PROJECT_DIR / 'Binaries' / args.configuration).rglob('RUCPackage.zip'),
                  key=lambda p: p.stat().st_mtime)
    if not rucs:
        raise RuntimeError(f"no RUCPackage.zip below Binaries/{args.configuration}, build with -buildRUCPackage first")
    return rucs[-1]


def pviTransfer(args, pil, timeout):
    pilFile = Path(tempfile.gettempdir()) / 'pvitransfer-br_server.pil'
    pilFile.write_text(pil, encoding='ascii')
    # Popen + wait instead of run: ARsim started by PVITransfer would inherit and hold the pipes
    proc = subprocess.Popen([args.pvi_transfer, '-silent', str(pilFile)])
    try:
        code = proc.wait(timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"PVITransfer did not finish within {timeout} s ({pilFile})")
    if code != 0:
        raise RuntimeError(f"PVITransfer failed with exit code {code} ({pilFile})")


def transferToPlc(args, ruc):
    print(f"== Transfer {ruc} to {args.target_ip} ({args.install_mode}), the PLC restarts", flush=True)
    # connection line as in the B&R/RUC examples (github.com/hilch/brsnmp/blob/master/examples.md); if it fails,
    # export a working transfer.pil from Automation Studio (Project > Export to RUC) and compare
    pviTransfer(args, '\r\n'.join([
        f'Connection "/IF=tcpip /LOPO=11159 /SA=113", '
        f'"/RT=3000 /AM=* /SDT=5 /DAIP={args.target_ip} /REPO=11159 /PT=11169 /ANSL=1", "WT=60"',
        f'Transfer "{ruc}", "InstallMode={args.install_mode} TryToBootInRUNMode=1 ResumeAfterRestart=1"',
    ]), 600)


def startArsim(args, ruc):
    arsimDir = Path(args.arsim_dir)
    print(f"== Start ARsim from {ruc} in {arsimDir}", flush=True)
    removeDir(arsimDir)
    # PVI 4.x syntax, PVI 6 (AS6) renamed it to OfflineCommissioning "<zip>", "ARSim", "DestinationDirectory='<dir>'";
    # its "Start=1" did not start ARsim reliably, so the loader is started here
    pviTransfer(args, f'CreateARsimStructure "{ruc}", "{arsimDir}"', args.start_timeout)
    loader = arsimDir / 'ar000loader.exe'
    if not loader.exists():
        raise RuntimeError(f"PVITransfer did not create {loader}")
    subprocess.Popen([str(loader)], cwd=arsimDir, creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))


def arsimRunning():
    out = subprocess.run(['tasklist', '/NH'], capture_output=True, text=True).stdout.lower()
    return 'ar000loader.exe' in out or 'ar000.exe' in out


def waitForServer(args, checkArsim):
    print(f"== Wait for the TCP server on {args.host}:{args.port}", flush=True)
    end = time.monotonic() + args.start_timeout
    while True:
        try:
            socket.create_connection((args.host, args.port), timeout=0.5).close()
            break
        except OSError:
            pass
        if checkArsim and not arsimRunning():
            raise RuntimeError(f"ARsim is not running, start ar000loader.exe by hand from {args.arsim_dir} to see why")
        if time.monotonic() > end:
            raise RuntimeError(f"no TCP server on {args.host}:{args.port} within {args.start_timeout} s")
        time.sleep(1)
    # the probe connection occupies the single client slot until the server notices the close
    time.sleep(2)


# ---------------------------------------------------------------- tests

class Rig:
    """ one TCP client: receive thread splitting 81-byte chunks, heartbeat thread """

    def __init__(self, args, connectTimeout=10.0):
        end = time.monotonic() + connectTimeout
        while True:
            try:
                self.sock = socket.create_connection((args.host, args.port), timeout=2)
                break
            except OSError:
                # the server needs a few cycles to listen again after a disconnect
                if time.monotonic() > end:
                    raise
                time.sleep(0.2)
        self.sock.settimeout(None)
        self.frames = queue.Queue()
        self.closed = threading.Event()
        self._beat = threading.Event()
        self._lock = threading.Lock()
        threading.Thread(target=self._rx, daemon=True).start()
        threading.Thread(target=self._heartbeat, daemon=True).start()
        # the OS accepts the connection at once, the PLC serves it only after it dropped the
        # previous client (up to heartbeat timeout + 1 s if that one vanished without a FIN)
        t0 = time.monotonic()
        self.status(timeout=4.0, what="first status after connect")
        if (delay := time.monotonic() - t0) > 0.5:
            print(f"    first status {delay:.1f} s after connect")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._beat.clear()
        try:
            self.sock.close()
        except OSError:
            pass

    def _rx(self):
        buf = bytearray()
        try:
            while data := self.sock.recv(4096):
                buf += data
                while len(buf) >= CHUNK:
                    self.frames.put((buf[0], bytes(buf[1:CHUNK]), time.monotonic()))
                    del buf[:CHUNK]
        except OSError:
            pass
        self.closed.set()

    def send(self, frame):
        msg = bytes(frame['msg'])
        with self._lock:
            self.sock.sendall(bytes([frame['id']]) + msg + bytes(PAYLOAD - len(msg)))

    def heartbeat(self, on):
        self._beat.set() if on else self._beat.clear()

    def _heartbeat(self):
        while not self.closed.is_set():
            if self._beat.is_set():
                try:
                    self.send(controlFrame(Control.HEARTBEAT))
                except OSError:
                    return
            time.sleep(HEARTBEAT_PERIOD)

    def wait(self, pred, timeout, what):
        """ returns the first truthy pred(id, payload, t) of the received frames """
        end = time.monotonic() + timeout
        while (left := end - time.monotonic()) > 0:
            try:
                fid, payload, t = self.frames.get(timeout=left)
            except queue.Empty:
                break
            if fid not in SERVER_IDS:
                raise AssertionError(f"unexpected frame id {fid}, stream misaligned")
            if result := pred(fid, payload, t):
                return result
        raise AssertionError(f"no {what} within {timeout} s")

    def status(self, pred=lambda s: True, timeout=1.5, what="status frame"):
        def match(fid, payload, t):
            if fid == STATUS_FRAME_ID:
                s = RigStatus.fromPayload(payload)
                if s is not None and pred(s):
                    return s
        return self.wait(match, timeout, what)

    def start(self, paramFrames=()):
        """ sends paramFrames and a start, returns the confirming status and the expected count/crc """
        self.heartbeat(True)
        before = self.status(what="status before start")
        for f in paramFrames:
            self.send(f)
        self.send(controlFrame(Control.START))
        s = self.status(lambda s: s.running and s.startSeq == (before.startSeq + 1) & 0xff,
                        what="running status with incremented start counter")
        return s, frameCrc(padded(paramFrames))


def padded(frames):
    """ the frames as the server receives them, see pywisp.TcpConnection.rigFrame """
    return [{'id': f['id'], 'msg': bytes(f['msg']) + bytes(PAYLOAD - len(f['msg']))} for f in frames]


def testIdleStatus(args):
    with Rig(args) as rig:
        s = rig.status(what="status while idle")
        assert s.version == 1, f"status version {s.version}"
        assert not s.running, "rig reports running right after connect"


def testStartSyncStop(args):
    # a frame id no module handles, only counted for the start confirmation
    params = [{'id': 20, 'msg': bytes(range(1, 9))}, {'id': 21, 'msg': b'\xff' * PAYLOAD}]
    with Rig(args) as rig:
        s, (count, crc) = rig.start(params)
        assert (s.startCount, s.startCrc) == (count, crc), \
            f"start confirmation {s.startCount}/{s.startCrc:#x}, expected {count}/{crc:#x}"

        rig.send(params[0])
        rig.send(syncFrame(42))
        s = rig.status(lambda s: s.syncId == 42, timeout=1.0, what="status for sync 42")
        count, crc = frameCrc(padded(params[:1]))
        assert (s.syncCount, s.syncCrc) == (count, crc), \
            f"sync confirmation {s.syncCount}/{s.syncCrc:#x}, expected {count}/{crc:#x}"
        assert s.running, "sync stopped the experiment"

        rig.send(controlFrame(Control.STOP))
        rig.status(lambda s: not s.running, what="idle status after stop")


def testSyncBeforeStart(args):
    """ as pywisp starts: parameters and a sync while idle, START once the sync is confirmed """
    params = [{'id': 20, 'msg': bytes(range(1, 9))}, {'id': 21, 'msg': b'\xff' * PAYLOAD}]
    with Rig(args) as rig:
        rig.heartbeat(True)
        before = rig.status(lambda s: not s.running, what="idle status before the sync")
        syncId = (before.syncId + 1) & 0xff
        for f in params:
            rig.send(f)
        rig.send(syncFrame(syncId))
        s = rig.status(lambda s: s.syncId == syncId, timeout=1.0, what=f"status for sync {syncId}")
        count, crc = frameCrc(padded(params))
        assert (s.syncCount, s.syncCrc) == (count, crc), \
            f"sync confirmation {s.syncCount}/{s.syncCrc:#x}, expected {count}/{crc:#x}"
        assert not s.running, "sync started the experiment"

        # the sync reset the frame counter, the start reports no frames
        s, _ = rig.start()
        try:
            assert (s.startCount, s.startCrc) == (0, 0), \
                f"start confirmation {s.startCount}/{s.startCrc:#x} after the sync, expected 0/0"
        finally:
            rig.send(controlFrame(Control.STOP))
        rig.status(lambda s: not s.running, what="idle status after stop")


def testDataFrames(args):
    """ the Test parameters (frame 12) come back in frame 10, whose time restarts at the start and grows by 100 ms """
    values = (1.5, 2.5, 320, 10)
    # as client/testbench.py Test.getParams
    params = [{'id': 12, 'msg': struct.pack('<dfhB', *values)}]
    with Rig(args) as rig:
        rig.start(params)
        samples = []
        try:
            end = time.monotonic() + 3.0
            while time.monotonic() < end:
                samples.append(rig.wait(lambda fid, p, t: fid == 10 and (struct.unpack_from('<LdfhB', p), t),
                                        1.0, "frame 10"))
        finally:
            # leave the rig idle for the next test
            rig.send(controlFrame(Control.STOP))

        assert samples[-1][0][1:] == values, f"frame 10 values {samples[-1][0][1:]}, sent {values}"
        times = [d[0] for d, _ in samples]
        assert times[0] < 1000, f"time not reset by the start: {times[0]} ms"
        steps = {b - a for a, b in zip(times, times[1:])}
        assert steps <= {CYCLE_MS}, f"time steps {sorted(steps)} ms, expected {CYCLE_MS}"
        rate = (times[-1] - times[0]) / 1000 / (samples[-1][1] - samples[0][1])
        print(f"    {len(samples)} frames, plc/wall-clock time = {rate:.2f}")
        if not 0.8 < rate < 1.25:
            print("    WARNING: the server does not run in real time, check the Cyclic#4 duration (100 ms)")


def testMissedHeartbeat(args):
    with Rig(args) as rig:
        rig.start()
        rig.heartbeat(False)
        t0 = time.monotonic()
        t = rig.wait(lambda fid, p, t: fid == CONTROL_FRAME_ID and p[0] == Control.STOP and t,
                     2.5, "missed-heartbeat frame (id 1, payload 0)")
        assert t - t0 > 0.8, f"stopped after {t - t0:.2f} s, before the heartbeat timeout"
        rig.status(lambda s: not s.running, what="idle status after missed heartbeat")
        assert rig.closed.wait(3.0), "PLC did not drop the client after the missed heartbeat"


def testReconnectAfterAbort(args):
    """ client vanishes while running, the next client gets a clean, aligned stream """
    rig = Rig(args)
    rig.start()
    rig.close()
    with Rig(args) as rig:
        rig.status(lambda s: not s.running, timeout=3.0, what="idle status after reconnect")
        # read for a while, wait() fails on misaligned frame ids
        try:
            rig.wait(lambda *a: False, 1.0, "")
        except AssertionError as e:
            if "misaligned" in str(e):
                raise


TESTS = [testIdleStatus, testStartSyncStop, testSyncBeforeStart, testDataFrames, testMissedHeartbeat,
         testReconnectAfterAbort]


def runTests(args):
    failed = 0
    for test in TESTS:
        print(f"{test.__name__} ...", flush=True)
        try:
            test(args)
            print("    PASS")
        except Exception as e:
            failed += 1
            print(f"    FAIL: {type(e).__name__}: {e}")
    print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
    return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', help="server address, default 127.0.0.1 or --target-ip")
    parser.add_argument('--port', type=int, default=50007)
    parser.add_argument('--target-ip', help="build for and install on this PLC instead of ARsim")
    parser.add_argument('--install-mode', default='Consistent', choices=['Consistent', 'ForceInitialInstallation'],
                        help="ForceInitialInstallation reinstalls everything if Consistent fails")
    parser.add_argument('--configuration', default='minimal')
    # default: searched below C:\BrAutomation, Automation Studio 4.4 (the project version) preferred
    parser.add_argument('--as-build', help="path of BR.AS.Build.exe")
    parser.add_argument('--pvi-transfer', help="path of PVITransfer.exe")
    parser.add_argument('--arsim-dir', default=os.path.join(tempfile.gettempdir(), 'arsim-br_server'))
    parser.add_argument('--start-timeout', type=int, default=120, help="[s] for PVITransfer and the server start")
    parser.add_argument('--skip-build', action='store_true', help="reuse the last RUCPackage.zip")
    parser.add_argument('--keep-running', action='store_true', help="leave ARsim running after the test")
    parser.add_argument('--test-only', action='store_true', help="no build, transfer or ARsim, test a running server")
    args = parser.parse_args()
    onPlc = bool(args.target_ip)
    args.host = args.host or args.target_ip or '127.0.0.1'

    if args.test_only:
        return runTests(args)
    if sys.platform != 'win32':
        parser.error("build and ARsim need Windows with Automation Studio, use --test-only elsewhere")

    useArsim = not onPlc
    arsimStarted = False
    try:
        if not args.skip_build:
            args.as_build = findTool(args.as_build, 'AS*/Bin-*/BR.AS.Build.exe', 'AS44', '--as-build')
        args.pvi_transfer = findTool(args.pvi_transfer, 'PVI/**/PVITransfer.exe', 'V4.4', '--pvi-transfer')
        if useArsim:
            stopArsim(args.arsim_dir)
        if not args.skip_build:
            build(args, onPlc)
        ruc = findRuc(args)
        if onPlc:
            transferToPlc(args, ruc)
        else:
            startArsim(args, ruc)
            arsimStarted = True
        waitForServer(args, checkArsim=useArsim)
        print("== Run tests", flush=True)
        return runTests(args)
    except (RuntimeError, OSError) as e:
        print(f"ERROR: {e}")
        return 1
    finally:
        if useArsim and not args.keep_running:
            stopArsim(args.arsim_dir)
        elif arsimStarted:
            print(f"== ARsim keeps running ({args.arsim_dir})")


if __name__ == '__main__':
    sys.exit(main())
