#pragma once

#include <comm/series.h>
#include <core/experiment.h>
#include <ctrl/trajectory.h>
#include <utils/later.h>

#include "doublependulum.h"

struct Pendulum {
    using Input = DoublePendulum::Input;
    using State = DoublePendulum::State;

    Later<Input> u;
    DoublePendulum p{};
    State& state{p.state};
    operator const State&() { return state; }
    void step(uint32_t, uint32_t dt) {
        p.setInput(u.get());
        p.compute(dt);
    }
};

struct Trajectory {
    using Reference = Pendulum::Input;
    Reference ref{};
    LinearTrajectory interp{};
    operator Reference&() { return ref; }
    void step(uint32_t time, uint32_t) {
        ref(0) = interp(time/1000.)[0];
    }
};

struct Model {
    Sink<Frame> &out;
    Pendulum p{
        .u = (Later<Pendulum::Input>)
            traj,
    };
    Trajectory traj;

    void reset(uint32_t) {
        p.state = Pendulum::State{0, 0, -0.1, 0.1,  -0.1, 0.1};
        traj.ref = Trajectory::Reference{};
    }

    void init(FrameRegistry &min) {
        // resets
        e.onEvent(e.INIT).call(*this, &Model::reset);
        // timesteps
        e.during(e.RUN).every(200, traj, &Trajectory::step);
        e.during(e.RUN).every(1, p, &Pendulum::step);

        e.during(e.RUN).every(25, *this, &Model::sendData);
        // frames
        min.setHandler(21, *this, &Model::getTrajData);
    }
    void sendData(uint32_t t, uint32_t dt) {
            Frame f{10};
            f.pack(t);
            f.pack<double>(p.state[0]);
            f.pack<double>(p.state[2]);
            f.pack<double>(p.state[4]);
            f.pack<double>(traj.ref[0]);
            out.push(std::move(f));

    }
    void getTrajData(Frame &f) {
        static SeriesUnpacker<double> su;
        auto buf = su.unpack(f);
        if (buf) {
            traj.interp.setData(std::move(*buf));
        }
    }
};
