/** @file Transport.cpp
 *
 */
#include "Transport.h"

//----------------------------------------------------------------------

void Transport::sendData() {
    Frame benchFrame(10);
    benchFrame.pack(this->_benchData.lTime);
    benchFrame.pack(this->_benchData.dValue1);
    benchFrame.pack(this->_benchData.fValue2);
    benchFrame.pack(this->_benchData.iValue3);
    benchFrame.pack(this->_benchData.cValue4);
    this->outputQueue.push(benchFrame);

    Frame trajRampFrame(11);
    trajRampFrame.pack(this->_benchData.lTime);
    trajRampFrame.pack(this->_trajData.dRampOutput);
    this->outputQueue.push(trajRampFrame);

    Frame trajSeriesFrame(15);
    trajSeriesFrame.pack(this->_benchData.lTime);
    trajSeriesFrame.pack(this->_trajData.dSeriesOutput);
    this->outputQueue.push(trajSeriesFrame);
}
//----------------------------------------------------------------------
void Transport::packArrayToFrame(unsigned char cId, unsigned char *cData, unsigned int iDataSize) {
    unsigned int iCompleteData = iDataSize * sizeof(unsigned char) + sizeof(unsigned int);
    unsigned int iCountPackages = iCompleteData / TRANSPORT_MAX_PAYLOAD + 1;

    unsigned int iCounter = 0;

    for (unsigned int i = 0; i < iCountPackages; i++) {
        if (i > 0) {
            Frame arrayFrame(cId);
            for (unsigned int j = 0; j < TRANSPORT_MAX_PAYLOAD; j++) {
                arrayFrame.pack(cData[iCounter++]);
            }
            this->outputQueue.push(arrayFrame);
        } else {
            Frame arrayFrame(cId);
            arrayFrame.pack(iCountPackages);
            for (unsigned int j = 0; j < TRANSPORT_MAX_PAYLOAD - sizeof(unsigned int); j++) {
                arrayFrame.pack(cData[iCounter++]);
            }
            this->outputQueue.push(arrayFrame);
        }
    }
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
            case 14:
                unpackTrajSeriesData(frame);
                break;
            default:;
        }
    }
}
//----------------------------------------------------------------------

void Transport::unpackExp(Frame frame) {
    frame.unPack(this->bActivateExperiment);
    this->_benchData.lTime = 0;
    while (!inputQueue.empty()) {
        inputQueue.pop();
    }
    while (!outputQueue.empty()) {
        outputQueue.pop();
    }
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
    double dStartValue = 0;
    unsigned long lStartTime = 0;
    double dEndValue = 0;
    unsigned long lEndTime = 0;
    frame.unPack(dStartValue);
    frame.unPack(lStartTime);
    frame.unPack(dEndValue);
    frame.unPack(lEndTime);
    _trajData.rampTraj.setTimesValues(lStartTime, lEndTime, dStartValue, dEndValue);

}
//----------------------------------------------------------------------

void Transport::unpackTrajSeriesData(Frame frame) {
    unsigned int iSize = 0;
    double dValue = 0.0;

    if (!this->bInComingSeriesData) {
        this->bInComingSeriesData = true;
        this->iInComingSeriesCounter = 0;
        frame.unPack(iSize);
        this->_trajData.seriesTraj.setSize(iSize);

        for (unsigned int i = 0; i < FRAME_LEN_DOUBLE - 1; i++) {
            frame.unPack(dValue);
            if (this->iInComingSeriesCounter < this->_trajData.seriesTraj.getSize()) {
                this->_trajData.seriesTraj.setTime(dValue, this->iInComingSeriesCounter);
            } else {
                this->_trajData.seriesTraj.setValue(dValue, this->iInComingSeriesCounter -
                                                            this->_trajData.seriesTraj.getSize());
            }
            this->iInComingSeriesCounter++;
        }
    } else {
        for (unsigned int i = 0; i < FRAME_LEN_DOUBLE; i++) {
            frame.unPack(dValue);
            if (this->iInComingSeriesCounter < this->_trajData.seriesTraj.getSize()) {
                this->_trajData.seriesTraj.setTime(dValue, this->iInComingSeriesCounter);
            } else {
                this->_trajData.seriesTraj.setValue(dValue, this->iInComingSeriesCounter -
                                                            this->_trajData.seriesTraj.getSize());
            }
            this->iInComingSeriesCounter++;
            if (this->iInComingSeriesCounter >= this->_trajData.seriesTraj.getCompleteSize()) {
                this->bInComingSeriesData = false;
                break;
            }
        }
    }
}
//----------------------------------------------------------------------
