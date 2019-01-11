/** @file Transport.cpp
 *
 */
#ifndef TRANSPORT_CPP
#define TRANSPORT_CPP

#include "Transport.h"

void Transport::init() {
    Serial.begin(115200);
    min_init_context(&this->ctx, 0);
}
//----------------------------------------------------------------------

void Transport::run() {
    int avl = 0, len = 0;
    if ((avl = Serial.available())) {
        len = Serial.readBytes(this->serialBuf, avl);
    }
    min_poll(&this->ctx, this->serialBuf, len);
}
//----------------------------------------------------------------------

void Transport::sendData() {

    uint8_t payload[20U];
    startFrame(payload);
    pack(this->_benchData.lTime);
    pack(this->_benchData.dValue1);
    pack(this->_benchData.fValue2);
    pack(this->_benchData.iValue3);
    pack(this->_benchData.cValue4);
    sendFrame(10);

    uint8_t payload[8U];
    startFrame(payload);
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
    delete frame;
}
//----------------------------------------------------------------------

void Transport::unpackExp(uint8_t *payload) {
    startFrame(payload);
    unPack(this->bActivateExperiment);
    this->_benchData.lTime = 0;
}
//----------------------------------------------------------------------

void Transport::unpackBenchData(uint8_t *payload) {
    startFrame(m_buf);
    unPack(this->_benchData.dValue1);
    unPack(this->_benchData.fValue2);
    unPack(this->_benchData.iValue3);
    unPack(this->_benchData.cValue4);
}
//----------------------------------------------------------------------

void Transport::unpackTrajRampData(uint8_t *m_buf) {
    startFrame(m_buf);
    unPack(this->_trajData.dStartValue);
    unPack(this->_trajData.lStartTime);
    unPack(this->_trajData.dEndValue);
    unPack(this->_trajData.lEndTime);
}
//----------------------------------------------------------------------

/*** MIN Callbacks ***/
uint16_t min_tx_space(uint8_t port) {
    return Serial.availableForWrite();
}
//----------------------------------------------------------------------

void min_tx_byte(uint8_t port, uint8_t byte) {
    Serial.write(&byte, 1);
}
//----------------------------------------------------------------------

void min_tx_start(uint8_t port) {}
//----------------------------------------------------------------------

void min_tx_finished(uint8_t port) {}
//----------------------------------------------------------------------

#ifdef TRANSPORT_PROTOCOL

uint32_t min_time_ms(void) {
    return millis();
}
//----------------------------------------------------------------------

#endif

void min_application_handler(uint8_t min_id, uint8_t *min_payload, uint8_t len_payload, uint8_t port) {
    Frame frame(min_id, payload, len_payload);
    transport.handleFrame(frame);
}
//----------------------------------------------------------------------

void Transport::pack(double dValue) {
    uPack.dVar = dValue;
    for (int i = 0; i < 8; ++i)
        data.payload[cCursor + i] = uPack.cVar[7 - i];

    cCursor += 8;
}

void Transport::pack(unsigned long lValue) {
    payload[cCursor + 0] = (unsigned char) ((lValue & 0xff000000UL) >> 24);
    payload[cCursor + 1] = (unsigned char) ((lValue & 0x00ff0000UL) >> 16);
    payload[cCursor + 2] = (unsigned char) ((lValue & 0x0000ff00UL) >> 8);
    payload[cCursor + 3] = (unsigned char) (lValue & 0x000000ffUL);

    cCursor += 4;
}

void Transport::pack(float fValue) {
    uPack.fVar1 = fValue;
    for (int i = 0; i < 4; ++i)
        data.payload[cCursor + i] = uPack.cVar[7 - i];

    cCursor += 4;
}

void Transport::pack(int iValue) {
    data.payload[cCursor + 0] = (unsigned char) ((iValue & 0x0000ff00UL) >> 8);
    data.payload[cCursor + 1] = (unsigned char) (iValue & 0x000000ffUL);

    cCursor += 2;
}

void Transport::pack(unsigned char cValue) {
    data.payload[cCursor + 0] = cValue;

    cCursor++;
}

void Transport::unPack(double &dValue) {
    lValue = ((uint32_t)(data.payload[cCursor + 0]) << 24) |
             ((uint32_t)(data.payload[cCursor + 1]) << 16) |
             ((uint32_t)(data.payload[cCursor + 2]) << 8) |
             (uint32_t)(data.payload[cCursor + 3]);

    cCursor += 4;
}

void Transport::unPack(unsigned long &lValue) {
    lValue = ((uint32_t)(data.payload[cCursor + 0]) << 24) |
             ((uint32_t)(data.payload[cCursor + 1]) << 16) |
             ((uint32_t)(data.payload[cCursor + 2]) << 8) |
             (uint32_t)(data.payload[cCursor + 3]);

    cCursor += 4;
}

void Transport::unPack(float &fValue) {
    lValue = ((uint32_t)(data.payload[cCursor + 0]) << 24) |
             ((uint32_t)(data.payload[cCursor + 1]) << 16) |
             ((uint32_t)(data.payload[cCursor + 2]) << 8) |
             (uint32_t)(data.payload[cCursor + 3]);

    cCursor += 4;
}

void Transport::unPack(int &iValue) {
    iValue = ((uint32_t)(data.payload[cCursor + 0]) << 8) |
             (uint32_t)(data.payload[cCursor + 1]);

    cCursor += 2;
}

void Transport::unPack(unsigned char &cValue) {
    cValue = data.payload[cCursor + 0];

    cCursor++;
}

void Transport::unPack(bool &bValue) {
    bValue = data.payload[cCursor + 0];

    cCursor++;
}

void Transport::startFrame(uint8_t *payload) {
    this->payload = payload;
    cCursor = 0;
}

void Transport::sendFrame(unsigned char id) {
    min_queue_frame(&this->ctx, id, payload, sizeof(payload));
}


#endif // TRANSPORT_CPP