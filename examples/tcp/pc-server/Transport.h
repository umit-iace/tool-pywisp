/** @file Transport.h
 *
 */
#ifndef TRANSPORT_H
#define TRANSPORT_H

#include "Frame.h"
#include "Utils.h"

//----------------------------------------------------------------------

/**
 * Class, that implements an intermediate layer for the communication between server and client.
 */
class Transport {
public:
    Transport(Queue<Frame> &inputQueue, Queue<Frame> &outputQueue) : inputQueue(inputQueue),
                                                                     outputQueue(outputQueue) {
    }

    /**
     * @brief Function for reading activity status of the experiment
     * @return Experiment active
     */
    bool runExp() { return this->bActivateExperiment; }

    /**
     * @brief Function that handles the received data and pack it in data structs
     */
    void handleFrames();

    /**
     * @brief Function for sending the data to the client
     */
    void sendData();

    /**
     * @brief struct of test rig data
     */
    struct benchData {
        unsigned long lTime = 0;                    ///< seconds since start of experiment
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
    bool bActivateExperiment = false;
    Queue<Frame> &inputQueue;
    Queue<Frame> &outputQueue;

    void unpackExp(Frame frame);

    void unpackBenchData(Frame frame);

    void unpackTrajRampData(Frame frame);

};


#endif //TRANSPORT_H
