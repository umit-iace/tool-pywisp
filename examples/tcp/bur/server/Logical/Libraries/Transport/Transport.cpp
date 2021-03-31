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
}

/*
 * @brief handles all frames arriving at the testbench
 */
void Transport::handleFrame(Frame frame)
{
	switch (frame.data.id) {
		case 1:
			unpackExp(frame);
			break;
		case 12:
			unpackBenchData(frame);
			break;
		case 13:
			unpackTrajRampData(frame);
			break;
		default:;
	}
}

/**
 * @brief unpacks experiment activation status and resets experiment time
 */
void Transport::unpackExp(Frame frame) {
	frame.unPack(expData.bActivateExperiment);
	benchData.lTime = 0;
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
 * @brief registers Server for handling outgoing frames
 */
void Transport::registerServer(Comm *serv)
{
	this->tcp = serv;
}
