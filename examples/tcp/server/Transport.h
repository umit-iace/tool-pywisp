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
    unsigned char var_byte[8];
} packunion;

struct Frame {
    unsigned char id;
    unsigned char payload[MAX_PAYLOAD];
};

class Transport {
public:
    Transport(Queue<Frame> &inputQueue, Queue<Frame> &outputQueue) : inputQueue(inputQueue),
                                                                     outputQueue(outputQueue) {
    }

    bool runExp() { return this->bActivateExperiment; }

    void handleFrames();

    void sendData();

    /**
     * @brief struct of test rig data
     */
    struct benchData {
        unsigned long lTime = 0;                    ///< milliseconds since start of experiment
        double dValue1 = 11.2;
        float fValue2 = 0.0;
        int iValue3 = 0;
        unsigned char cValue4 = 0;
    } _benchData;

    /**
     * @brief struct of trajectory data
     */
    struct trajData {
        double dStartValue = 0.0;          ///< start value of the trajectory
        unsigned long lStartTime = 0;      ///< start time of the trajectory
        double dEndValue = 0.0;            ///< end value of the trajectory
        unsigned long lEndTime = 0;        ///< end time of the trajectory
        double dOutput = 0.0;              ///< output value of the trajectory
    } _trajData;

private:
    bool bActivateExperiment = false;
    Queue<Frame> &inputQueue;
    Queue<Frame> &outputQueue;

    void unpackExp(unsigned char *payload);

    void unpackBenchData(unsigned char *payload);

    void unpackTrajRampData(unsigned char *payload);

    void sendFrame(unsigned char id, unsigned char payload[MAX_PAYLOAD]);
};


#endif //TRANSPORT_H
