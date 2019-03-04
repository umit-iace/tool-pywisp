from connect import socket_bind_listen, socket_accept, get_sender_receiver
from uinput import get_input_device
from system import ode_rhs
from threading import ThreadError, active_count
from scipy.integrate import ode
import numpy as np
import time


def thread_debug(debug):
    if debug:
        if active_count() > 4:
            raise ThreadError("Too many threads.")

        if not all([th.is_alive() for th in [input_, receiver]]):
            raise ThreadError("Not all required threads are alive.")


def cycle(t):
    global sender, solver, input_, cycle_time

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

# system setup
solver = ode(ode_rhs)
x_init = np.array([0, 0, np.pi, 0, np.pi, 0])
x_magic = np.array([0, 0, 1e-3, 0, 0, 0])
input_ = get_input_device()
cycle_time = 0.02
tolerance = cycle_time * 0.1

# communication setup
msg_length = 80
socket = socket_bind_listen(50007)
connection = socket_accept(socket)
sender, receiver = get_sender_receiver(connection, msg_length)

# init main loop
start_time = time.time()
last_reset = start_time
loop_start = start_time
loop_time_max = 0
rt_errors = 0
debug = False
start = False
ts = 0

while True:
    # receive data if available
    msg = receiver.get_all()

    # simulate system up to t
    cycle_start = time.time()
    t = cycle_start - start_time
    if (len(msg) or input_.reset()) and cycle_start - last_reset > 2:
        start = True
        solver.set_initial_value(x_init - x_magic, t)
        last_reset = cycle_start
    elif start:
        start = cycle(t)

    # send data if available
    send_start = time.time()
    sender.send_all()
    thread_debug(debug)

    # lock loop to cycle time
    loop_finished = time.time()
    loop_time = loop_finished - loop_start
    slack_time = cycle_time - loop_time
    if loop_time < cycle_time:
        time.sleep(slack_time)
    elif abs(slack_time) > tolerance:
        rt_errors = rt_errors + 1
    loop_end = time.time()

    # print status info
    if loop_time > loop_time_max:
        loop_time_max = loop_time
    print("loop: {:10.6f} <{:10.6f} /{:10.6f}\t | \t"
          "cycle: {:10.6f} /{:10.6f}\t | \t"
          "receive: {:10.6f}\t | \t"
          "send: {:10.6f}\t | \t"
          "timeouts in total {}".format(
        loop_time, loop_time_max, loop_end - loop_start,
        send_start - cycle_start, cycle_time,
        cycle_start - loop_start,
        loop_finished - send_start,
        rt_errors))
    loop_start = loop_end

