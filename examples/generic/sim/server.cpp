/** @file server.cpp
 *
 * Copyright (c) 2023 IACE
 */
#include <sys/comm.h>
#include <cstdlib>
#include <core/experiment.h>
#include "model.h"

#include "comm/min.h"
#include "comm/bufferutils.h"
#include "comm/line.h"

TTY tty{"/dev/tty"};
UDP udp{"127.0.0.1", 45670};

struct Support {
    Support();
    void init();
    LineDelimiter lineout;
    Min min;
};

Support::Support()
    : lineout{tty}
    , min{.in = udp, .out = udp}
{}
void Support::init() {
    /* e.setHeartbeatTimeout(500, min.out); */
    k.every(500,
            [](uint32_t time, uint32_t) {
                uint32_t freq{1000};
                static bool state{false};
                freq = e.state==e.IDLE?2000:freq;
                freq = e.state==e.RUN?500:freq;
                if (time % freq == 0) {
                    state = !state;
                    k.log.info("led (would be) %s", state?"on":"off");
                }
            });
    e.onEvent(e.STOP).call([](uint32_t){abort();});
}

Kernel k;
Support support;
Experiment e{&support.min.reg};

int main() {
    support.init();
    k.initLog(support.lineout);
    k.every(1, support.min, &Min::poll);

    Model model{support.min.out};
    model.init(support.min.reg);
    k.run();
}
