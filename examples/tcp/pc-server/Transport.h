/** @file Transport.h
 *
 */
#ifndef TRANSPORT_H
#define TRANSPORT_H

#include "Frame.h"
#include "Trajectory.h"
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
        RampTrajectory rampTraj = RampTrajectory();         ///< ramp trajectory object
        SeriesTrajectory seriesTraj = SeriesTrajectory();   ///< series trajectory object
        double dRampOutput = 0.0;                           ///< output value of the ramp trajectory
        double dSeriesOutput = 0.0;                         ///< output value of the series trajectory
    } _trajData;                                            ///< instance of heater trajectory data

private:
    bool bActivateExperiment = false;
    Queue<Frame> &inputQueue;
    Queue<Frame> &outputQueue;

    void unpackExp(Frame frame);

    void unpackBenchData(Frame frame);

    void unpackTrajRampData(Frame frame);

    void unpackTrajSeriesData(Frame frame);

    bool bInComingSeriesData = false;
    unsigned int iInComingSeriesCounter = 0;

};

#endif //TRANSPORT_H
