/** @file Model.h
 *
 * Copyright (c) 2024 IACE
 */
#ifndef MODEL_H
#define MODEL_H

#include <comm/series.h>
#include <core/experiment.h>
#include <ctrl/trajectory.h>
#include <utils/later.h>


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

#endif //MODEL_H
