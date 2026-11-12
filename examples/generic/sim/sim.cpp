/** @file sim.cpp
 *
 * Copyright (c) 2024 IACE
 */
#include <comm/fixedframe.h>
#include <core/experiment.h>
#include <sys/comm.h>
#include <sys/sim.h>
#include "model.h"
#include "Pendulum.h"
#include "NonLinDoublePendulum.h"

TTY tty{"/dev/tty"};
UDP udp{"127.0.0.1", 45670};
// pywisp's TcpConnection sends 1 byte id + 80 bytes payload per frame, no MIN
TCP tcp{"127.0.0.1", 45671};
FixedFrame<> tcpFrames{.in = tcp, .out = tcp};
Pendulum::Input u;

void Pendulum::updateState(uint32_t time, uint32_t dt_ms) {
    double dt = dt_ms / 1000.;

    state = state + dt * NonLinDoublePendulum::step(state, u);

    k.log.print("%g, %g, %g, %g, %g, %g, %g, %g\n",
                state(0), state(1),
                state(2), state(3),
                state(4), state(5),
                u,
                dt
    );
}

void Pendulum::reset() {
    state = Pendulum::State{0, 0, -0.1, 0.1,  -0.1, 0.1};
}

void Pendulum::setInput(double val) {
    u = val;
}

/** frames to pywisp go to the link that received the last frame */
struct Reply : Sink<Frame> {
    Sink<Frame> *to;
    Reply(Sink<Frame> &to) : to{&to} {}
    bool full() override { return to->full(); }
    using Sink::push;
    void push(Frame &&f) override { to->push(std::move(f)); }
} reply{support.min.out};

/** both links feed the same registry */
void poll(uint32_t, uint32_t) {
    while (!support.min.in.empty()) {
        reply.to = &support.min.out;
        support.min.reg.handle(support.min.in.pop());
    }
    while (!tcpFrames.in.empty()) {
        reply.to = &tcpFrames.out;
        support.min.reg.handle(tcpFrames.in.pop());
    }
}

Support::Support() : min{.in = udp, .out = udp }, out{reply} {}

void Support::init() {
    // stop the experiment if pywisp sends no heartbeat (HeartbeatTime in default.sreg) for 1 s
    e.setHeartbeatTimeout(1000, out);
    e.onEvent(e.STOP).call([](uint32_t) {
        u = Pendulum::Input{};
    });

    e.onEvent(e.INIT).call([](uint32_t) {
        k.log.print("starting simulation");
    });
}

Kernel k;
Support support;
Experiment e{&support.min.reg};

int main(int argc, char *argv[]) {
    k.initLog(tty);
    k.setTimeStep(getSimTimeStep(argc, argv));
    k.every(1, poll);
    support.init();

    Model m;
    m.init();
    k.run();
}
