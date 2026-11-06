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
	Transport() : tcp(0) { reset(); }

	void handleFrame(const Frame &frame);

	void sendData();

	void registerServer(Comm *serv);

	/** forgets a partially received series, call while no client is connected */
	void reset();

	private:
	Comm *tcp;
	unsigned short seriesCount;	///< number of values of the series being received
	unsigned short seriesRecv;	///< number of values of it received so far

	void unpackBenchData(Frame frame);

	void unpackTrajRampData(Frame frame);

	void unpackTrajSeriesData(Frame frame);
};

#endif //TRANSPORT_CLASS_H
