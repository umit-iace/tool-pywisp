#ifndef COMM_H
#define COMM_H

#include "Transport/Frame.h"

#define MAX_PAYLOAD (80)

class Comm {
public:
	virtual void handleFrame(Frame frame) = 0;
};

#endif
