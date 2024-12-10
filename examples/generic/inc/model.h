/** @file Model.h
 *
 * Copyright (c) 2024 IACE
 */
#ifndef MODEL_H
#define MODEL_H

#include <comm/min.h>
#include <core/experiment.h>
#include <utils/later.h>
#include <comm/series.h>

#include "support.h"
#include "Pendulum.h"
#include "TrajType.h"


struct Model {
    enum Config {TRAJ};

    Pendulum doublePendulum {
        .input = (Later<Pendulum::Input>) trajType.out,
    };

    TrajType trajType;

    FrameRegistry &fr {support.min.reg};
    Min::Out &out {support.min.out};

    void reset(uint32_t) {
        doublePendulum.reset();
        trajType.reset();
    }

    void init() {
        // reset
        e.onEvent(e.INIT).call(*this, &Model::reset);

        e.during(e.RUN).every(1, doublePendulum, &Pendulum::tick);

        // timesteps
        e.during(e.RUN).every(2, trajType, &TrajType::step);

        e.during(e.RUN).every(20, *this, &Model::sendModelData);
        e.during(e.RUN).every(20, *this, &Model::sendTrajData);

        fr.setHandler(10, *this, &Model::setModelData);
        fr.setHandler(20, *this, &Model::setTrajType);
        fr.setHandler(21, trajType, &TrajType::setData);
    }

    void sendModelData(uint32_t time, uint32_t) {
        Frame f{15};
        f.pack(time);
        f.pack(doublePendulum.state(0));
        f.pack(doublePendulum.state(2));
        f.pack(doublePendulum.state(4));
        f.pack(doublePendulum.in);
        out.push(f);
    }

    void sendTrajData(uint32_t time, uint32_t) {
        Frame f{25};
        f.pack(time);
        f.pack(trajType.des[0]);
        f.pack(trajType.des[1]);
        out.push(f);
    }

    void setModelData(Frame &f) {
        auto config = f.unpack<uint8_t>();

        switch (config) {
            case Config::TRAJ: {
                doublePendulum.input = (Later<Pendulum::Input>) trajType.out;
                break;
            }
        }
    }

    void setTrajType(Frame &f) {
        trajType.mkType(f.unpack<TrajType::Type>());
    }
};

#endif //MODEL_H
