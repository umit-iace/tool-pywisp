import numpy as np
import time
from connect import socket_bind_listen, socket_accept, get_sender_receiver
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
    global sender, solver, input_

    control = input_.control() * 10
    solver.set_f_params(control)
    x = solver.integrate(t)

    if not solver.successful():
        print("!!! Solver not successsful !!!")
        time.sleep(1)
        return False

    if np.abs(x[0]) > 1.7:
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
    xInit = np.array([.4, 0, np.pi, 0, np.pi, 0])
    xMagic = np.array([0, 0, 1e-3, 0, 0, 0])
    input_ = get_input_device()
    cycleTime = 0.02
    tolerance = cycleTime * 0.1

    # communication setup
    msgLength = 80
    socket = socket_bind_listen(50007)
    connection = socket_accept(socket)
    sender, receiver = get_sender_receiver(connection, msgLength)

    # init main loop
    status_string = ("loop: {:10.6f} <{:10.6f} /{:10.6f}\t | \t"
                     "cycle: {:10.6f} /{:10.6f}\t | \t"
                     "receive: {:10.6f}\t | \t"
                     "send: {:10.6f}\t | \t"
                     "timeouts in total {}")
    startTime = time.time()
    lastReset = startTime
    loopStart = startTime
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
        t = cycleStart - startTime
        if (len(msg) or input_.reset()) and cycleStart - lastReset > 2:
            start = True
            solver.set_initial_value(xInit - xMagic, t)
            lastReset = cycleStart

        elif start:
            start = cycle(t)

            if input_.cheat() and not system.feedForwardIsRunning(t) and cycleStart - lastReset < 2:
                system.ffLastStart = t
                solver.set_initial_value(xInit, t)

        # send data if available
        sendStart = time.time()
        sender.send_all()
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
        print(status_string.format(loopTime, loopTimeMax, loopEnd - loopStart,
                                   sendStart - cycleStart, cycleTime,
                                   cycleStart - loopStart,
                                   loopFinished - sendStart,
                                   rtErrors))
        loopStart = loopEnd
