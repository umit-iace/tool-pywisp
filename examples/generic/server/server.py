import numpy as np
import time
from connect import socketBindListen, socketAccept, getSenderReceiver
from scipy.integrate import ode
from system import System
from threading import ThreadError, active_count
from uinput import get_input_device


def threadDebug(debug):
    if debug:
        if active_count() > 4:
            raise ThreadError("Too many threads.")

        if not all([th.is_alive() for th in [input_, receiver]]):
            raise ThreadError("Not all required threads are alive.")


def cycle(t):
    global sender, solver, input_, cycleTime

    control = input_.control()
    solver.set_f_params(control)
    x = solver.integrate(t)

    if not solver.successful():
        print("!!! Solver not successsful !!!")
        time.sleep(1)
        return False

    if np.abs(x[0]) > 1.5:
        x[0] = x[0] * -1
        solver.set_initial_value(x, t)

    sender.put(10,
               [int(t) * 1000,
                float(x[0]),
                float(x[2]),
                float(x[4]),
                float(control)],
               ">Ldddd")

    return True


if __name__ == '__main__':
    # system setup
    system = System()
    solver = ode(system.rhs)
    xInit = np.array([0, 0, np.pi, 0, np.pi, 0])
    xMagic = np.array([0, 0, 1e-3, 0, 0, 0])
    input_ = get_input_device()
    cycleTime = 0.02
    tolerance = cycleTime * 0.1

    # communication setup
    msgLength = 80
    socket = socketBindListen(50007)
    connection = socketAccept(socket)
    sender, receiver = getSenderReceiver(connection, msgLength)

    # init main loop
    start_time = time.time()
    lastReset = start_time
    loopStart = start_time
    loopTimeMax = 0
    rtErrors = 0
    debug = False
    start = False
    ts = 0

    while True:
        # receive data if available
        msg = receiver.getAll()

        # simulate system up to t
        cycleStart = time.time()
        t = cycleStart - start_time
        if (len(msg) or input_.reset()) and cycleStart - lastReset > 2:
            start = True
            solver.set_initial_value(xInit - xMagic, t)
            lastReset = cycleStart
        elif start:
            start = cycle(t)

        # send data if available
        sendStart = time.time()
        sender.sendAll()
        threadDebug(debug)

        # lock loop to cycle time
        loopFinished = time.time()
        loopTime = loopFinished - loopStart
        slack_time = cycleTime - loopTime
        if loopTime < cycleTime:
            time.sleep(slack_time)
        elif abs(slack_time) > tolerance:
            rtErrors = rtErrors + 1
        loopEnd = time.time()

        # print status info
        if loopTime > loopTimeMax:
            loopTimeMax = loopTime
        print("loop: {:10.6f} <{:10.6f} /{:10.6f}\t | \t"
              "cycle: {:10.6f} /{:10.6f}\t | \t"
              "receive: {:10.6f}\t | \t"
              "send: {:10.6f}\t | \t"
              "timeouts in total {}".format(loopTime, loopTimeMax, loopEnd - loopStart,
                                            sendStart - cycleStart, cycleTime,
                                            cycleStart - loopStart,
                                            loopFinished - sendStart,
                                            rtErrors))
        loopStart = loopEnd
