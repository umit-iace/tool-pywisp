#define _BUR_USE_DECLARATION_IN_IEC
#ifdef _DEFAULT_INCLUDES
#include "AsDefault.h"
#endif
#include "Transport.h"

/**
 * @brief Method that defines and sends all testbench frames
 */
void Transport::sendData() {
	Frame benchFrame(10);
	benchFrame.pack(benchData.lTime);
	benchFrame.pack(benchData.dValue1);
	benchFrame.pack(benchData.fValue2);
	benchFrame.pack(benchData.iValue3);
	benchFrame.pack(benchData.cValue4);
	benchFrame.pack(benchData.dValueNan);
	benchFrame.pack(benchData.dValueInf);
	tcp->handleFrame(benchFrame);

	Frame trajFrame(11);
	trajFrame.pack(benchData.lTime);
	trajFrame.pack(trajData.dOutput);
	tcp->handleFrame(trajFrame);

	Frame seriesFrame(15);
	seriesFrame.pack(benchData.lTime);
	seriesFrame.pack(trajData.dSeriesOutput);
	tcp->handleFrame(seriesFrame);
}

/*
 * @brief handles all frames arriving at the testbench, the control frames (id 1) are handled by the TcpIpServer
 */
void Transport::handleFrame(const Frame &frame)
{
	switch (frame.data.id) {
		case 12:
			unpackBenchData(frame);
			break;
		case 13:
			unpackTrajRampData(frame);
			break;
		case 14:
			unpackTrajSeriesData(frame);
			break;
		default:;
	}
}

void Transport::unpackBenchData(Frame frame) {
	frame.unPack(benchData.dValue1);
	frame.unPack(benchData.fValue2);
	frame.unPack(benchData.iValue3);
	frame.unPack(benchData.cValue4);
}

void Transport::unpackTrajRampData(Frame frame) {
	frame.unPack(trajData.dStartValue);
	frame.unPack(trajData.lStartTime);
	frame.unPack(trajData.dEndValue);
	frame.unPack(trajData.lEndTime);
}

/**
 * @brief receives the series as pywisp.utils.packArrayToFrame(14, data, 80, 8, 2) sends it: the first frame holds
 * the number of values (unsigned short) and up to 9 doubles, the following ones up to 10 doubles each.
 * The values are all times [ms], then all values. The series is used once it is complete.
 */
void Transport::unpackTrajSeriesData(Frame frame) {
	const unsigned short maxCount = sizeof(trajData.adSeries) / sizeof(trajData.adSeries[0]);
	unsigned int n = MAX_PAYLOAD / 8;
	if (seriesRecv >= seriesCount) {
		frame.unPack(seriesCount);
		seriesRecv = 0;
		trajData.uiSeriesPoints = 0;
		n = (MAX_PAYLOAD - 2) / 8;
	}
	for (unsigned int i = 0; i < n && seriesRecv < seriesCount; ++i, ++seriesRecv) {
		double d = 0;
		frame.unPack(d);
		/* values of a series that is too long are dropped, it is not used */
		if (seriesRecv < maxCount)
			trajData.adSeries[seriesRecv] = d;
	}
	if (seriesRecv >= seriesCount && seriesCount <= maxCount)
		trajData.uiSeriesPoints = seriesCount / 2;
}

void Transport::reset() {
	seriesCount = 0;
	seriesRecv = 0;
}

/**
 * @brief registers Server for handling outgoing frames
 */
void Transport::registerServer(Comm *serv)
{
	this->tcp = serv;
}
