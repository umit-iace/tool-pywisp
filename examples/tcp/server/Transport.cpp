//
// Created by Jens Wurm on 04.01.19.
//

#include "Transport.h"

#define DECLARE_BUF() unsigned char m_buf[MAX_PAYLOAD], m_cursor = 0
#define PACK8(v) (m_buf[m_cursor] = (v), m_cursor++)
#define PACK16(v) (encode_16(*((unsigned long*)&(v)), m_buf + m_cursor), m_cursor += 2)
#define PACK32(v) (encode_32(*((unsigned long*)&(v)), m_buf + m_cursor), m_cursor += 4)
#define PACK64(v) (encode((v), m_buf + m_cursor), m_cursor +=8)

#define DECLARE_UNPACK() unsigned char m_cursor = 0
#define UNPACK8(v) (v) = payload[m_cursor]; m_cursor++
#define UNPACK16(v) (decode((v), payload + m_cursor), m_cursor += 2)
#define UNPACK32(v) (decode((v), payload + m_cursor), m_cursor += 4)
#define UNPACK64(v) (decode((v), payload + m_cursor), m_cursor += 8)

#define SEND_FRAME(v) (sendFrame((v), m_buf))

void encode(double data, unsigned char buf[]) {
    packunion.var_double = data;
    for (int i = 0; i < 8; ++i)
        buf[i] = packunion.var_byte[7 - i];
}


void encode_32(unsigned long data, unsigned char buf[]) {
    buf[0] = (unsigned char) ((data & 0xff000000UL) >> 24);
    buf[1] = (unsigned char) ((data & 0x00ff0000UL) >> 16);
    buf[2] = (unsigned char) ((data & 0x0000ff00UL) >> 8);
    buf[3] = (unsigned char) (data & 0x000000ffUL);
}

void encode_16(unsigned long data, unsigned char buf[]) {
    buf[0] = (unsigned char) ((data & 0x0000ff00UL) >> 8);
    buf[1] = (unsigned char) (data & 0x000000ffUL);
}

void decode(float &var, unsigned char buf[]) {
    for (int i = 0; i < 4; ++i)
        packunion.var_byte[7 - i] = buf[i];
    var = packunion.var_float;
}

void decode(double &var, unsigned char buf[]) {
    for (int i = 0; i < 8; ++i)
        packunion.var_byte[7 - i] = buf[i];
    var = packunion.var_double;
}

void decode(unsigned long &var, unsigned char buf[]) {
    var = ((uint32_t)(buf[0]) << 24) | ((uint32_t)(buf[1]) << 16) | ((uint32_t)(buf[2]) << 8) | (uint32_t)(buf[3]);
}

void decode(int &var, unsigned char buf[]) {
    var = ((uint32_t)(buf[0]) << 8) | (uint32_t)(buf[1]);
}

void Transport::sendData() {
    {
        DECLARE_BUF();
        PACK32(this->_benchData.lTime);
        PACK64(this->_benchData.dValue1);
        PACK32(this->_benchData.fValue2);
        PACK16(this->_benchData.iValue3);
        PACK8(this->_benchData.cValue4);
        SEND_FRAME(10);
    }
    {
        DECLARE_BUF();
        PACK32(this->_benchData.lTime);
        PACK64(this->_trajData.dOutput);
        SEND_FRAME(11);
    }
}

void Transport::sendFrame(unsigned char id, unsigned char payload[MAX_PAYLOAD]) {
    Frame frame;
    frame.id = id;
    for (int i = 0; i < MAX_PAYLOAD; i++) {
        frame.payload[i] = payload[i];
    }
    this->outputQueue.push(frame);
}

void Transport::handleFrames() {
    while (!inputQueue.empty()) {
        Frame frame = inputQueue.pop();
        switch (frame.id) {
            case 1:
                unpackExp(frame.payload);
                break;
            case 12:
                unpackBenchData(frame.payload);
                break;
            case 13:
                unpackTrajRampData(frame.payload);
                break;
            default:;
        }
    }
}

void Transport::unpackExp(unsigned char *payload) {
    DECLARE_UNPACK();
    UNPACK8(this->bActivateExperiment);
    this->_benchData.lTime = 0;
}

void Transport::unpackBenchData(unsigned char *payload) {
    DECLARE_UNPACK();
    UNPACK64(this->_benchData.dValue1);
    UNPACK32(this->_benchData.fValue2);
    UNPACK16(this->_benchData.iValue3);
    UNPACK8(this->_benchData.cValue4);
}

void Transport::unpackTrajRampData(unsigned char *payload) {
    DECLARE_UNPACK();
    UNPACK64(this->_trajData.dStartValue);
    UNPACK32(this->_trajData.lStartTime);
    UNPACK64(this->_trajData.dEndValue);
    UNPACK32(this->_trajData.lEndTime);
}
