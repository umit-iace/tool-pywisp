#ifndef TRANSPORT_CLASS_H
#define TRANSPORT_CLASS_H

#include "../Comm.h"
#include "Frame.h"
/** \file Transport.h
 *  \class Transport
 *  \brief Class for packing and unpacking pyWisp communication data
 */

class Transport: public Comm {
	public:
	void handleFrame(Frame frame);

	void sendData();
	
	void registerServer(Comm *serv);

	private:
	Comm *tcp;

	void unpackExp(Frame frame);

	void unpackBenchData(Frame frame);

	void unpackTrajRampData(Frame frame);
};

#endif //TRANSPORT_CLASS_H
