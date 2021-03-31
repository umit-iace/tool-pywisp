/** @file Frame.h
 *
 */
#ifndef FRAME_H
#define FRAME_H

#include "define.h"
#include "Utils.h"

/**
 * Class, that implements a byte wise frame that is interchanged by connection. The frame has an id and a payload
 * for the specific data. The data is stored as an byte array. It implements all functions to store and unpack
 * the data to and from byte wise array. The id represents the identification of the frame.
 */
class Frame {

public:
    struct {
        unsigned char id;
        unsigned char payload[TRANSPORT_MAX_PAYLOAD];
    } data;

    Frame(unsigned char id) {
        data.id = id;
        cCursor = 0;
    }

    Frame() {
        cCursor = 0;
    }

    template<typename T>
    void pack(T value) {
        auto *origin = (uint8_t *) &value;
        for (int i = sizeof(T) - 1; i >= 0; --i) {
            data.payload[cCursor + i] = *origin++;
        }
        cCursor += sizeof(T);
    }

    template<typename T>
    void unPack(T &value) {
        auto *dest = (uint8_t *) &value;
        for (int i = sizeof(T) - 1; i >= 0; --i) {
            *dest++ = data.payload[cCursor + i];
        }
        cCursor += sizeof(T);
    }

private:
    unsigned char cCursor = 0;

    union {
        double dVar;
        struct {
            float fVar2;
            float fVar1;
        };
        unsigned char cVar[8];
    } uPack;

};

#endif //FRAME_H
