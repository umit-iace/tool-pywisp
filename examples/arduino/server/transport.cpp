/** @file transport.cpp
 *
 * Copyright (c) 2018 IACE
 */
#ifndef TRANSPORT_CPP
#define TRANSPORT_CPP

#include "transport.h"

//\cond false
#define DECLARE_BUF(size) uint8_t m_buf[(size)]; uint8_t m_control = (size); uint8_t m_cursor = 0

#define PACK8(v) (m_buf[m_cursor] = (v), m_cursor++)
#define PACK16(v) (encode_16(*((uint16_t*)&(v)), m_buf + m_cursor), m_cursor += 2U)
#define PACK32(v) (encode_32(*((uint32_t*)&(v)), m_buf + m_cursor), m_cursor += 4U)
#define SEND_FRAME(id) (min_queue_frame(&this->ctx, (id), m_buf, m_control))

#define DECLARE_UNPACK() uint8_t m_cursor = 0; uint32_t _m_tmp

#define UNPACK8(v, type) (v) = *(type*)&m_buf[m_cursor]; m_cursor++
#define UNPACK16(v, type) _m_tmp = decode_16(m_buf + m_cursor); m_cursor += 2U; (v) = *(type*)&_m_tmp
#define UNPACK32(v, type) _m_tmp = decode_32(m_buf + m_cursor); m_cursor += 4U; (v) = *(type*)&_m_tmp

static void encode_32(uint32_t data, uint8_t buf[])
{
    buf[0] = (uint8_t)((data & 0xff000000UL) >> 24);
    buf[1] = (uint8_t)((data & 0x00ff0000UL) >> 16);
    buf[2] = (uint8_t)((data & 0x0000ff00UL) >> 8);
    buf[3] = (uint8_t)(data & 0x000000ffUL);
}

static void encode_16(uint32_t data, uint8_t buf[])
{
    buf[0] = (uint8_t)((data & 0x0000ff00UL) >> 8);
    buf[1] = (uint8_t)(data & 0x000000ffUL);
}

static uint32_t decode_32(uint8_t buf[])
{
    uint32_t res;
    res = ((uint32_t)(buf[0]) << 24) | ((uint32_t)(buf[1]) << 16) | ((uint32_t)(buf[2]) << 8) | (uint32_t)(buf[3]);
    return res;
}

static uint16_t decode_16(uint8_t buf[])
{
    uint16_t res;
    res = ((uint16_t)(buf[0]) << 8) | (uint16_t)(buf[1]);
    return res;
}
//\endcond

void Transport::init()
{
  Serial.begin(115200);
  min_init_context(&this->ctx, 0);
}

void Transport::run()
{
  int avl = 0, len = 0;
  if ((avl = Serial.available())) {
    len = Serial.readBytes(this->serialBuf, avl);
  }
  min_poll(&this->ctx, this->serialBuf, len);
}

void Transport::sendData()
{
  {
    DECLARE_BUF(20U);
    PACK32(this->_benchData.lTime);
    for (int i = 0; i < 4; ++i)
    {
      PACK32(this->_benchData.dTm[i]);
    }
    SEND_FRAME(10);
  }
  {
    DECLARE_BUF(20U);
    PACK32(this->_benchData.lTime);
    for (int i = 0; i < 4; ++i)
    {
      PACK32(this->_benchData.dTw[i]);
    }
    SEND_FRAME(11);
  }
  {
    DECLARE_BUF(20U);
    PACK32(this->_benchData.lTime);
    for (int i = 0; i < 4; ++i)
    {
      PACK32(this->_benchData.dTwi[i]);
    }
    SEND_FRAME(12);
  }
  {
    DECLARE_BUF(12U);
    PACK32(this->_benchData.lTime);
    PACK32(this->_benchData.dTamb);
    PACK32(this->_benchData.dv);
    SEND_FRAME(13);
  }
}

void Transport::handleFrame(uint8_t id, uint8_t *payload, uint8_t payloadLen)
{
  switch (id) {
    case 1:
      unpackExp(payload);
      break;
    default:
      min_queue_frame(&this->ctx, ++id, payload, payloadLen);
  }
}

//\cond false
void Transport::unpackExp(uint8_t *m_buf)
{
  DECLARE_UNPACK();
  UNPACK8(this->bActivateExperiment, uint8_t);
  this->_benchData.lTime = 0;
}

/*** MIN Callbacks ***/
uint16_t min_tx_space(uint8_t port)
{
  return Serial.availableForWrite();
}

void min_tx_byte(uint8_t port, uint8_t byte)
{
    Serial.write(&byte, 1);
}

void min_tx_start(uint8_t port) {}

void min_tx_finished(uint8_t port) {}

#ifdef TRANSPORT_PROTOCOL
uint32_t min_time_ms(void)
{
  return millis();
}
#endif

void min_application_handler(uint8_t min_id, uint8_t *min_payload, uint8_t len_payload, uint8_t port)
{
  transport.handleFrame(min_id, min_payload, len_payload);
}
//\endcond

#endif // TRANSPORT_CPP