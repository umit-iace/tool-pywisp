/* codegen.c */

/* AUTOMATICALLY GENERATED C CODE; DO NOT EDIT */

#include "gen.h"

/* Network ordering conversion functions (compiler should inline) */
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

/* Macros for packing and unpacking frame buffers */
#define DECLARE_BUF(size) uint8_t m_buf[(size)]; uint8_t m_control = (size); uint8_t m_cursor = 0

#define PACK8(v) (m_buf[m_cursor] = (v), m_cursor++)
#define PACK16(v) (encode_16((v), m_buf + m_cursor), m_cursor += 2U)
#define PACK32(v) (encode_32((v), m_buf + m_cursor), m_cursor += 4U)

#define SEND_FRAME(id) (min_tx_frame((id), m_buf, m_control))

#define DECLARE_UNPACK() uint8_t m_cursor = 0

#define UNPACK8(v) ((v) = (int8_t)m_buf[m_cursor], m_cursor++)
#define UNPACK16(v) ((v) = (int16_t)decode_16(m_buf + m_cursor), m_cursor += 2U)
#define UNPACK32(v) ((v) = (int32_t)decode_32(m_buf + m_cursor), m_cursor += 4U
#define UNPACKU8(v) ((v) = m_buf[m_cursor], m_cursor++)
#define UNPACKU16(v) ((v) = decode_16(m_buf + m_cursor), m_cursor += 2U)
#define UNPACKU32(v) ((v) = decode_32(m_buf + m_cursor), m_cursor += 4U)

/* Update bit bytes for frames */
uint8_t min_f1_update_byte_0;
uint8_t min_f3_update_byte_0;
uint8_t min_f7_update_byte_0;

/* Signal frame queueing functions */
void min_queue_frame_f3(void)
{
    DECLARE_BUF(9U);
    PACK8(min_f3_update_byte_0);
    min_f3_update_byte_0 = 0;
    PACK32(min_i1_var);
    PACK32(min_i1_var);
    SEND_FRAME(56U);
}
void min_queue_frame_f7(void)
{
    DECLARE_BUF(8U);
    PACK8(min_f7_update_byte_0);
    min_f7_update_byte_0 = 0;
    PACK32(min_s4_var);
    PACK16(min_s5_var);
    PACK8(min_s6_var);
    SEND_FRAME(3U);
}

/* Functions for sending raw frames */
void min_queue_frame_f5(uint8_t buf[], uint8_t control)
{
    if(min_f5_period_counter == 0) {
        min_tx_frame(1, buf, control);
        min_f5_period_counter = 3;
    }
}
void min_queue_frame_f6(uint8_t buf[], uint8_t control)
{
    if(min_f6_period_counter == 0) {
        min_tx_frame(2, buf, control);
        min_f6_period_counter = 3;
    }
}

/* Functions for unpacking raw frames do not appear here: they are callbacks into user code */

/* Frame sending period guard counters for raw and forced transmit frames */
uint8_t min_f3_period_counter;
uint8_t min_f5_period_counter;
uint8_t min_f6_period_counter;


/* Frame sending period counters for normal periodic frames */
uint8_t min_f7_period_counter;

/* Signal variables declarations (both input and output) */

uint8_t min_s1_var;
uint16_t min_s2_var;
uint32_t min_s3_var;
uint32_t min_i1_var;
uint32_t min_s4_var;
int16_t min_s5_var;
uint8_t min_s6_var;

/* Functions for sending force transmit signals */


/* Functions for unpacking signal frames */

static void min_unpack_frame_f1(uint8_t m_buf[])
{
    DECLARE_UNPACK();
    UNPACKU8(min_f1_update_byte_0);
    UNPACKU8(min_s1_var);
    UNPACKU16(min_s2_var);
    UNPACKU32(min_s3_var);
}
static void min_unpack_frame_f2(uint8_t m_buf[])
{
    DECLARE_UNPACK();
}

void min_input(void)
{
    /* Handle all the outstanding characters in the input buffer */
    while(uart_receive_ready()) {
        uint8_t byte;
        uart_receive(&byte, 1U);
        min_rx_byte(byte);
    }
}

void min_frame_received(uint8_t buf[], uint8_t control, uint8_t id)
{
    switch(id) {
        case 0U:
            min_unpack_frame_f1(buf);
            break;
        case 57U:
            min_unpack_frame_f2(buf);
            break;
        case 4U:
            min_unpack_frame_f8(buf, control);
            break;
    }
}

void min_initialize(void)
{
    min_f3_period_counter == 0;
    min_f5_period_counter == 0;
    min_f6_period_counter == 0;
    min_f7_period_counter == 1U;
}

/* Handle counters for period guarded frames (raw and force transmit) and also periodic signal frames */
void min_output(void)
{
    if(min_f3_period_counter) {
        min_f3_period_counter--;
    }
    if(min_f5_period_counter) {
        min_f5_period_counter--;
    }
    if(min_f6_period_counter) {
        min_f6_period_counter--;
    }
    if(--min_f7_period_counter == 0) {
        min_f7_period_counter = 7U;
        min_queue_frame_f7();
    }
}