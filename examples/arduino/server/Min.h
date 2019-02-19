// MIN Protocol v3.0.
//
// MIN is a lightweight reliable protocol for exchanging information from a microcontroller (MCU) to a host.
// It is designed to run on an 8-bit MCU but also scale up to more powerful devices. A typical use case is to
// send data from a UART on a small MCU over a UART-USB converter plugged into a PC host. A Python implementation
// of host code is provided (or this code could be compiled for a PC).
//
// MIN supports frames of 0-255 bytes (with a lower limit selectable at compile time to reduce RAM). MIN frames
// have identifier values between 0 and 63.
//
// A transport layer is compiled in. This provides sliding window reliable transmission of frames.

#ifndef MIN_H
#define MIN_H

#include <stdint.h>
#include <Arduino.h>

#define DEBUG_PRINT 0
#if DEBUG_PRINT

void debug_print(const char *msg, ...);

#else
#define debug_print(...)
#endif

struct TransportFrame {
    uint32_t last_sent_time_ms;             // When frame was last sent (used for re-send timeouts)
    uint16_t payload_offset;                // Where in the ring buffer the payload is
    uint8_t payload_len;                    // How big the payload is
    uint8_t min_id;                         // ID of frame
    uint8_t seq;                            // Sequence number of frame
};

class TransportFIFO {
public:
    TransportFIFO(uint8_t size) {
        frames = new struct TransportFrame[size];
        now = 0;
    }

    void reset();


    struct TransportFrame *frames;
    uint32_t last_sent_ack_time_ms;
    uint32_t last_received_anything_ms;
    uint32_t last_received_frame_ms;
    uint32_t dropped_frames;                // Diagnostic counters
    uint32_t spurious_acks;
    uint32_t sequence_mismatch_drop;
    uint32_t resets_received;
    uint16_t n_ring_buffer_bytes;           // Number of bytes used in the payload ring buffer
    uint16_t ring_buffer_tail_offset;       // Tail of the payload ring buffer
    uint8_t n_frames;                       // Number of frames in the FIFO
    uint8_t head_idx;                       // Where frames are taken from in the FIFO
    uint8_t tail_idx;                       // Where new frames are added
    uint8_t sn_min;                         // Sequence numbers for transport protocol
    uint8_t sn_max;
    uint8_t rn;
    uint32_t now;
};

class Min {
public:
    Min(uint8_t frames, uint16_t frame_data, uint8_t max_payload, uint8_t serialBufLen) : transport_fifo(frames) {
        // Initialize context
        rx_header_bytes_seen = 0;
        rx_frame_state = SEARCHING_FOR_SOF;

        // Counters for diagnosis purposes
        transport_fifo.reset();

        this->max_payload = max_payload;
        payloads_ring_buffer = new uint8_t[frame_data];
        rx_frame_payload_buf = new uint8_t[max_payload];      // Payload received so far
        transport_fifo_max_frames = frames;
        transport_fifo_max_frames_mask = frames - 1;
        transport_fifo_max_frame_data = frame_data;
        transport_fifo_max_frame_data_mask = frame_data - 1;

        serialBuf = new uint8_t[serialBufLen];
    }

    void initSerial(HardwareSerial &serial) {
        this->serial = &serial;

        this->serial->begin(115200);
    }


private:
    TransportFIFO transport_fifo;           // T-MIN queue of outgoing frames
    uint32_t ack_retransmit_timeout_ms = 25;
    uint32_t frame_retransmit_timeout_ms = 400;
    uint32_t max_window_size = 16;
    uint32_t idle_timeout_ms = 3000;
    uint32_t transport_fifo_max_frames_mask;
    uint32_t transport_fifo_max_frame_data_mask;
    uint32_t transport_fifo_max_frames = 16;
    uint32_t transport_fifo_max_frame_data;
    uint8_t max_payload = 40;

    uint8_t *serialBuf;
    uint8_t *payloads_ring_buffer;

    HardwareSerial *serial;

    uint8_t *rx_frame_payload_buf;      // Payload received so far
    uint32_t rx_frame_checksum;                     // Checksum received over the wire
    uint32_t rx_checksum;               // Calculated checksum for receiving frame
    uint32_t tx_checksum;               // Calculated checksum for sending frame
    uint8_t rx_header_bytes_seen;                   // Countdown of header bytes to reset state
    uint8_t rx_frame_state;                         // State of receiver
    uint8_t rx_frame_payload_bytes;                 // Length of payload received so far
    uint8_t rx_frame_id_control;                    // ID and control bit of frame being received
    uint8_t rx_frame_seq;                           // Sequence number of frame being received
    uint8_t rx_frame_length;                        // Length of frame
    uint8_t rx_control;                             // Control byte
    uint8_t tx_header_byte_countdown;               // Count out the header bytes

    // Special protocol bytes
    enum {
        HEADER_BYTE = 0xaaU,
        STUFF_BYTE = 0x55U,
        EOF_BYTE = 0x55U,
    };

    // Receiving state machine
    enum {
        SEARCHING_FOR_SOF,
        RECEIVING_ID_CONTROL,
        RECEIVING_SEQ,
        RECEIVING_LENGTH,
        RECEIVING_PAYLOAD,
        RECEIVING_CHECKSUM_3,
        RECEIVING_CHECKSUM_2,
        RECEIVING_CHECKSUM_1,
        RECEIVING_CHECKSUM_0,
        RECEIVING_EOF,
    };

    enum {
        // Top bit must be set: these are for the transport protocol to use
        // 0x7f and 0x7e are reserved MIN identifiers.
        ACK = 0xffU,
        RESET = 0xfeU,
        TRANSPORT_FRAME = 0x80U,
    };


    void crc32_init_context(uint32_t &checksum);

    void crc32_step(uint32_t &checksum, uint8_t byte);

    uint32_t crc32_finalize(uint32_t &checksum);

    void stuffed_tx_byte(uint8_t byte);

    void on_wire_bytes(uint8_t id_control, uint8_t seq, uint8_t *payload_base, uint16_t payload_offset,
                       uint16_t payload_mask, uint8_t payload_len);

    void transport_fifo_pop();

    TransportFrame *transport_fifo_push(uint8_t data_size);

    TransportFrame *transport_fifo_get(uint8_t n);

    void transport_fifo_send(TransportFrame *frame);

    void send_ack();

    void send_reset();

    void transport_fifo_reset();

    void transport_reset(bool inform_other_side);

public:
    bool queue_frame(uint8_t min_id, uint8_t *payload, uint8_t payload_len);

    void poll();

private:
    TransportFrame *find_retransmit_frame();

    void valid_frame_received();

    void rx_byte(uint8_t byte);


    uint32_t on_wire_size(uint32_t p) {
        return p + 11U;
    }

    void tx_byte(uint8_t byte);

    uint32_t time_ms();

    uint16_t tx_space();

    void application_handler(uint8_t min_id, uint8_t *min_payload, uint8_t len_payload);

public:
    void add_application_function(
            void(*application_function)(uint8_t min_id, uint8_t *min_payload, uint8_t len_payload)) {
        this->application_function = application_function;
    }

private:
    void (*application_function)(uint8_t min_id, uint8_t *min_payload, uint8_t len_payload);

};

#endif //MIN_H
