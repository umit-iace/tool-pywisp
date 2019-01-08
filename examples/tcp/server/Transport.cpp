//
// Created by Jens Wurm on 04.01.19.
//

#include "Transport.h"

/**< Macros zum Setzen der Cursoren damit Buffer geschrieben werden*/
#define DECLARE_BUF() unsigned char m_buf[MAX_PAYLOAD], m_cursor = 0

#define PACK32(v) (encode_32(*((unsigned long*)&(v)), m_buf + m_cursor), m_cursor += 4)
#define PACK64(v) (encode((v), m_buf + m_cursor), m_cursor +=8)

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


void Transport::sendData() {
//    logText("Sende Daten:");
//    logText(std::to_string(this->_benchData.lTime));
//    logText(std::to_string(this->_benchData.dValue1));

    {
        DECLARE_BUF();
        PACK32(this->_benchData.lTime);
        PACK64(this->_benchData.dValue1);
        SEND_FRAME(46);
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
