/** @file Transport.cpp
 *
 */
#ifndef TRANSPORT_CPP
#define TRANSPORT_CPP

#include "Transport.h"

void Transport::run() {
    cMin.poll();
}
//----------------------------------------------------------------------

void Transport::sendData() {

    startFrame(15U);
    pack(this->_benchData.lTime);
    pack(this->_benchData.dValue1);
    pack(this->_benchData.fValue2);
    pack(this->_benchData.iValue3);
    pack(this->_benchData.cValue4);
    sendFrame(10);

    startFrame(8U);
    pack(this->_benchData.lTime);
    pack(this->_trajData.dOutput);
    sendFrame(11);
}
//----------------------------------------------------------------------

void Transport::handleFrame(uint8_t id, uint8_t *payload, uint8_t payloadLen) {
    switch (id) {
        case 1:
            unpackExp(payload);
            break;
        case 12:
            unpackBenchData(payload);
            break;
        case 13:
            unpackTrajRampData(payload);
            break;
        default:;
    }
}
//----------------------------------------------------------------------

void Transport::unpackExp(uint8_t *payload) {
    uint8_t iData = 0;
    startFrame(payload);
    unPack(iData);
    if (iData & 2) {
        this->keepaliveTime = this->_benchData.lTime;
    } else {
        this->bActivateExperiment = iData & 1;
        this->_benchData.lTime = 0;
    }

}
//----------------------------------------------------------------------

void Transport::unpackBenchData(uint8_t *payload) {
    startFrame(payload);
    unPack(this->_benchData.dValue1);
    unPack(this->_benchData.fValue2);
    unPack(this->_benchData.iValue3);
    unPack(this->_benchData.cValue4);
}
//----------------------------------------------------------------------

void Transport::unpackTrajRampData(uint8_t *payload) {
    startFrame(payload);
    unPack(this->_trajData.dStartValue);
    unPack(this->_trajData.lStartTime);
    unPack(this->_trajData.dEndValue);
    unPack(this->_trajData.lEndTime);
}
//----------------------------------------------------------------------

void Transport::pack32(uint32_t data, uint8_t payload[]) {
    payload[0] = (uint8_t)((data & 0xff000000UL) >> 24);
    payload[1] = (uint8_t)((data & 0x00ff0000UL) >> 16);
    payload[2] = (uint8_t)((data & 0x0000ff00UL) >> 8);
    payload[3] = (uint8_t)(data & 0x000000ffUL);
}
//----------------------------------------------------------------------

void Transport::pack(double dValue) {
    pack32(*((uint32_t * ) & dValue), payload + cCursor);

    cCursor += 4U;
}
//----------------------------------------------------------------------

void Transport::pack(unsigned long lValue) {
    pack32(*((uint32_t * ) & lValue), payload + cCursor);

    cCursor += 4U;
}
//----------------------------------------------------------------------

void Transport::pack(float fValue) {
    pack32(*((uint32_t * ) & fValue), payload + cCursor);

    cCursor += 4U;
}
//----------------------------------------------------------------------

void Transport::pack(int iValue) {
    payload[cCursor + 0] = (uint8_t)(((uint16_t) iValue & 0x0000ff00UL) >> 8);
    payload[cCursor + 1] = (uint8_t)((uint16_t) iValue & 0x000000ffUL);

    cCursor += 2U;
}
//----------------------------------------------------------------------

void Transport::pack(unsigned char cValue) {
    payload[cCursor + 0] = cValue;

    cCursor++;
}
//----------------------------------------------------------------------

uint32_t Transport::unPack32() {
    uint32_t res = ((uint32_t)(payload[cCursor + 0]) << 24) |
                   ((uint32_t)(payload[cCursor + 1]) << 16) |
                   ((uint32_t)(payload[cCursor + 2]) << 8) |
                   (uint32_t)(payload[cCursor + 3]);

    return res;
}
//----------------------------------------------------------------------

void Transport::unPack(double &dValue) {
    uint32_t res = unPack32();
    dValue = *(double *) &res;

    cCursor += 4U;
}
//----------------------------------------------------------------------

void Transport::unPack(unsigned long &lValue) {
    uint32_t res = unPack32();
    lValue = *(unsigned long *) &res;

    cCursor += 4U;
}
//----------------------------------------------------------------------

void Transport::unPack(float &fValue) {
    uint32_t res = unPack32();
    fValue = *(float *) &res;

    cCursor += 4U;
}
//----------------------------------------------------------------------

void Transport::unPack(int &iValue) {
    iValue = ((uint32_t)(payload[cCursor + 0]) << 8) |
             (uint32_t)(payload[cCursor + 1]);

    cCursor += 2U;
}
//----------------------------------------------------------------------

void Transport::unPack(unsigned char &cValue) {
    cValue = payload[cCursor + 0];

    cCursor++;
}
//----------------------------------------------------------------------

void Transport::unPack(bool &bValue) {
    bValue = payload[cCursor + 0];

    cCursor++;
}
//----------------------------------------------------------------------

void Transport::startFrame(unsigned char cSize) {
    this->payload = new uint8_t[cSize];
    this->payloadSize = cSize;
    cCursor = 0;
}
//----------------------------------------------------------------------

void Transport::startFrame(uint8_t *payload) {
    this->payload = payload;
    cCursor = 0;
}
//----------------------------------------------------------------------

void Transport::sendFrame(unsigned char id) {
    cMin.queue_frame(id, payload, payloadSize);
    delete[] payload;
}
//----------------------------------------------------------------------

#endif // TRANSPORT_CPP
