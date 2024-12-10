/** @file Pendulum.h
 *
 * Copyright (c) 2024 IACE
 */
#ifndef PENDULUM_H
#define PENDULUM_H

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
