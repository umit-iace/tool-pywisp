from threading import ThreadError, active_count
from uinput import get_input_device
from connect import Sender, Receiver, get_socket, establish_connection
from system import rhs
from scipy.integrate import ode
import numpy as np
import time


def cycle():
    global ts, start, start_time, receiver, sender, solver, input_, delay
    new_ts = time.time()
    print("Execute cycle {} seconds after last call.".format(new_ts - ts))
    ts = new_ts
    t = new_ts - start_time

    if receiver.new_msg():
        frame = receiver.receive()
        id = frame[0]
        data = frame[1:]
        print('received message:: \t\t id: {!r}; \t\t data: {!r}'.format(id, data))

        # start experiment with the first received message
        start = True
        solver.set_initial_value([0, 0, np.pi, 0, np.pi, 0], t - delay)

    if start:

        if input_.reset():
            print("reset solver")
            solver.set_initial_value([0, 0, np.pi, 0, np.pi, 0], t - delay)

        control = input_.control()
        solver.set_f_params(control)
        x = solver.integrate(t)

        if not solver.successful():
            raise ValueError("Solver not successsful.")

        sender.send(10,
                    [int(t) * 1000,
                     float(x[0]),
                     float(x[2]),
                     float(x[4]),
                     float(control)],
                    ">Ldddd")

        if x[0] > 1.5:
            reset = x
            reset[0] = -1.5
            solver.set_initial_value(reset, t)

        elif x[0] < -1.5:
            reset = x
            reset[0] = 1.5
            solver.set_initial_value(reset, t)


# solver setup
def ode_rhs(t, y, u):
    return rhs(y, (u,), 0, 0, 0)
solver = ode(ode_rhs)

# init main loop
input_ = get_input_device()
start_time = time.time()
msg_length = 80
start = False
delay = 0.01
ts = 0

# wait for connection
socket = get_socket(50007)
connection, sender, receiver = establish_connection(socket, msg_length)

while True:

    if active_count() > 4:
        raise ThreadError("Too many threads.")

    if not all([th.is_alive() for th in [input_, sender, receiver]]):
        raise ThreadError("Not all required threads are alive.")

    cycle()
    time.sleep(delay)
