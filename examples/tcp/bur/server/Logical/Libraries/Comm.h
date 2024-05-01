/**
 * @file Comm.h
 */
#ifndef COMM_H
#define COMM_H

#include "Transport/Frame.h"

/**
 * @class Comm
 * @brief defines an interface class which lets the TcpIpServer communicate with the transport protocol
 */
class Comm {
	public:
	virtual void handleFrame(Frame frame) = 0;
};

#endif
