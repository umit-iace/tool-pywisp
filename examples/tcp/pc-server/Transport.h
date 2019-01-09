//
// Created by Jens Wurm on 04.01.19.
//

#ifndef TRANSPORT_H
#define TRANSPORT_H

#include "utils.h"

void encode(double data, unsigned char buf[]);

void encode_32(unsigned long data, unsigned char buf[]);

void encode_16(unsigned long data, unsigned char buf[]);


class Frame {

public:
    unsigned char id;
    unsigned char payload[MAX_PAYLOAD];

    Frame(unsigned char id): id(id) {
        cCursor = 0;
    }

    Frame() {
        cCursor = 0;
    }

    void pack(double dValue) {
        encode(dValue, payload);
        cCursor += 8;
    };

    void pack(unsigned long lValue) {
        encode(lValue, payload + cCursor);
        cCursor += 4;
    };

    void pack(float fValue) {
        encode(fValue, payload + cCursor);
        cCursor += 4;
    };

    void pack(int iValue) {
        encode(iValue, payload + cCursor);
        cCursor += 2;
    };

    void pack(unsigned char cValue) {
        encode(cValue, payload + cCursor);
        cCursor++;
    };

    void unPack(double dValue) {
        decode(dValue, payload + cCursor);
        cCursor += 8;
    }

    void unPack(unsigned long lValue) {
        decode(lValue, payload + cCursor);
        cCursor += 4;
    }

    void unPack(float fValue) {
        decode(fValue, payload + cCursor);
        cCursor += 4;
    }

    void unPack(int iValue) {
        decode(iValue, payload + cCursor);
        cCursor += 2;
    }

    void unPack(unsigned char cValue) {
        decode(cValue, payload + cCursor);
        cCursor++;
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

    void decode(float &fVar, const unsigned char cBuf[]) {
        for (int i = 0; i < 4; ++i)
            uPack.cVar[7 - i] = cBuf[i];
        fVar = uPack.fVar1;
    }

    void decode(double &dVar, const unsigned char cBuf[]) {
        for (int i = 0; i < 8; ++i)
            uPack.cVar[7 - i] = cBuf[i];
        dVar = uPack.dVar;
    }

    void decode(unsigned long &lVar, const unsigned char cBuf[]) {
        lVar = ((uint32_t) (cBuf[0]) << 24) |
               ((uint32_t) (cBuf[1]) << 16) |
               ((uint32_t) (cBuf[2]) << 8) |
               (uint32_t) (cBuf[3]);
    }

    void decode(int &iVar, const unsigned char cBuf[]) {
        iVar = ((uint32_t) (cBuf[0]) << 8) |
               (uint32_t) (cBuf[1]);
        std::cout << iVar << std::endl;
    }

    void decode(unsigned char &cVar, const unsigned char cBuf[]) {
        cVar = cBuf[0];
    }

    void encode(const double dData, unsigned char cBuf[]) {
        uPack.dVar = dData;
        for (int i = 0; i < 8; ++i)
            cBuf[i] = uPack.cVar[7 - i];
    }

    void encode(const unsigned long lData, unsigned char cBuf[]) {
        cBuf[0] = (unsigned char) ((lData & 0xff000000UL) >> 24);
        cBuf[1] = (unsigned char) ((lData & 0x00ff0000UL) >> 16);
        cBuf[2] = (unsigned char) ((lData & 0x0000ff00UL) >> 8);
        cBuf[3] = (unsigned char) (lData & 0x000000ffUL);
    }

    void encode(const int iData, unsigned char cBuf[]) {
        cBuf[0] = (unsigned char) ((iData & 0x0000ff00UL) >> 8);
        cBuf[1] = (unsigned char) (iData & 0x000000ffUL);
    }

    void encode(const unsigned char cData, unsigned char cBuf[]) {
        cBuf[0] = cData;
    }


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
        double dValue1 = 21342354.2213;
        float fValue2 = 556.2;
        int iValue3 = 244;
        unsigned char cValue4 = 12;
    } _benchData;

    /**
     * @brief struct of trajectory data
     */
    struct trajData {
        double dStartValue = 0.0;          ///< start value of the trajectory
        unsigned long lStartTime = 0;      ///< start time of the trajectory
        double dEndValue = 0.0;            ///< end value of the trajectory
        unsigned long lEndTime = 0;        ///< end time of the trajectory
        double dOutput = 85.0;             ///< output value of the trajectory
    } _trajData;

private:
    bool bActivateExperiment = true;
    Queue<Frame> &inputQueue;
    Queue<Frame> &outputQueue;

    void unpackExp(Frame frame);

    void unpackBenchData(Frame frame);

    void unpackTrajRampData(Frame frame);

};


#endif //TRANSPORT_H
