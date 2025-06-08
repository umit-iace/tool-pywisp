/** @file Pendulum.h
 *
 * Copyright (c) 2024 IACE
 */
#ifndef PENDULUM_H
#define PENDULUM_H

#include <utils/later.h>
#include <array>

struct Pendulum {
    using State = std::array<double, 6>;
    State state{};

    using Input = double;
    Later<Input> input;
    double in;

    void tick(uint32_t time, uint32_t dt) {
        this->in = input.get();
        auto u = this->in;
        setInput(u);

        updateState(time, dt);
    };

    void reset();
    void setInput(double);
    void updateState(uint32_t time, uint32_t dt);
};

#endif //PENDULUM_H
