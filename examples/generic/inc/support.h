#pragma once
#include <comm/min.h>

extern struct Support {
    Support();
    void init();
    Min min;
    /// where frames to pywisp go, min.out or, if the rig has several links, the active one
    Sink<Frame> &out;
} support;
