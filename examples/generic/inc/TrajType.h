/** @file TrajType.h
 *
 * Copyright (c) 2024 IACE
 */
#ifndef TRAJTYPE_H
#define TRAJTYPE_H

#include <ctrl/trajectory.h>
#include <variant>

#include "Pendulum.h"

struct TrajType {
    using Des = Reference<2>;
    using Out = Pendulum::Input;

    Des des;
    Out out{};

    std::variant<LinearTrajectory, SmoothTrajectory> traj{2};
    enum Type:uint8_t {NONE, LIN, POLY} type{NONE};

    void step(uint32_t time, uint32_t) {
        double t = time * 0.001;
        switch(type) {
            case LIN: {
                des = std::get<LinearTrajectory>(traj).getValue(t);
                break;
            }
            case POLY: {
                des = std::get<SmoothTrajectory>(traj).getValue(t);
                break;
            }
            case NONE:
                return;
        }
        out = des[0];
    }

    void reset() {
        this->out = {};
        this->des = {0, 0};
    }

    void mkType(Type t) {
        if (type == t) return;
        type = (Type) t;
        reset();

        switch(t) {
            case LIN: {
                traj = LinearTrajectory(2);
                break;
            }
            case POLY: {
                traj = SmoothTrajectory({3, -2}, 3);
                break;
            }
            case NONE: break;
        }
    }

    void setData(Frame &f) {
        static SeriesUnpacker<double> dData;
        if (dData.unpack(f)) {
            switch(type) {
                case LIN: {
                    std::get<LinearTrajectory>(traj).setData(std::move(dData.buf));
                    break;
                }
                case POLY: {
                    std::get<SmoothTrajectory>(traj).setData(std::move(dData.buf));
                    break;
                }
                case NONE: break;
            }
        }
    }
};

#endif //TRAJTYPE_H
