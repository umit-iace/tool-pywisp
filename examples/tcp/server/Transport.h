//
// Created by Jens Wurm on 04.01.19.
//

#ifndef TRANSPORT_H
#define TRANSPORT_H

#include "utils.h"

void encode(double data, unsigned char buf[]);

void encode_32(unsigned long data, unsigned char buf[]);

void encode_16(unsigned long data, unsigned char buf[]);

union {
    double var_double;
    struct {
        float var_float2;
        float var_float;
    };
    struct {
        unsigned long var_ulong2;
        unsigned long var_ulong;
    };
    struct {
        int var_int2;
        int :16;
        int :16;
        int var_int;
    };
    unsigned char var_byte[8];

} packunion;

struct Frame {
    unsigned char id;
    unsigned char payload[MAX_PAYLOAD];
};

class Transport {
public:
    Transport(Queue<Frame> &outputQueue) : outputQueue(outputQueue) {
    }

    bool runExp() { return this->bActivateExperiment; }

    void sendData();

    /**
     * @brief struct of test rig data
     */
    struct benchData {
        unsigned long lTime = 0;                    ///< milliseconds since start of experiment
        double dValue1 = 11.2;
        bool bReset = false;                        ///< reset flag for new experiment start
    } _benchData;

private:
    bool bActivateExperiment = true;
    Queue<Frame> &outputQueue;

    void sendFrame(unsigned char id, unsigned char payload[MAX_PAYLOAD]);
};


#endif //TRANSPORT_H
