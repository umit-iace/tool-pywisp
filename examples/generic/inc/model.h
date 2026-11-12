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
    Sink<Frame> &out {support.out};

    void reset(uint32_t) {
        doublePendulum.reset();
        trajType.reset();
    }

    void init() {
        // status frames, pywisp shows whether the rig responds and checks the start
        e.enableStatus(out);
        // log messages of these levels are sent to pywisp too, the cyclic prints (NONE) stay local
        e.enableLog(out, Logger::bit(Logger::INFO) | Logger::bit(Logger::WARN) | Logger::bit(Logger::ERROR));

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
            default:
                k.log.warn("unknown model config %u\n", config);
        }
    }

    void setTrajType(Frame &f) {
        auto t = f.unpack<TrajType::Type>();
        static const char *names[] = {"NONE", "LIN", "POLY"};
        if (t > TrajType::POLY) {
            k.log.error("unknown trajectory type %u\n", (unsigned) t);
            return;
        }
        trajType.mkType(t);
        k.log.info("trajectory type set to %s\n", names[t]);
    }
};

#endif //MODEL_H
