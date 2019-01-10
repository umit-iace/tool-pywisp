/** @file Transport.cpp
 *
 * Copyright (c) 2018 IACE
 */
#include "Transport.h"

void Transport::sendData() {
    Frame benchFrame(10);
    benchFrame.pack(this->_benchData.lTime);
    benchFrame.pack(this->_benchData.dValue1);
    benchFrame.pack(this->_benchData.fValue2);
    benchFrame.pack(this->_benchData.iValue3);
    benchFrame.pack(this->_benchData.cValue4);
    this->outputQueue.push(benchFrame);

    Frame trajFrame(11);
    trajFrame.pack(this->_benchData.lTime);
    trajFrame.pack(this->_trajData.dOutput);
    this->outputQueue.push(trajFrame);
}
//----------------------------------------------------------------------

void Transport::handleFrames() {
    while (!inputQueue.empty()) {
        Frame frame = inputQueue.pop();
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
}
//----------------------------------------------------------------------

void Transport::unpackExp(Frame frame) {
    frame.unPack(this->bActivateExperiment);
    this->_benchData.lTime = 0;
}
//----------------------------------------------------------------------

void Transport::unpackBenchData(Frame frame) {
    frame.unPack(this->_benchData.dValue1);
    frame.unPack(this->_benchData.fValue2);
    frame.unPack(this->_benchData.iValue3);
    frame.unPack(this->_benchData.cValue4);
}
//----------------------------------------------------------------------

void Transport::unpackTrajRampData(Frame frame) {
    frame.unPack(this->_trajData.dStartValue);
    frame.unPack(this->_trajData.lStartTime);
    frame.unPack(this->_trajData.dEndValue);
    frame.unPack(this->_trajData.lEndTime);
}
//----------------------------------------------------------------------
