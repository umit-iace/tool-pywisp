/** @file server.ino
 *
 */

// Includes
#include "TimerOne.h"
#include "Transport.h"

//----------------------------------------------------------------------

// System parameter
const unsigned long lDt = 100;              ///< Sampling step [ms]
const unsigned long lKeepalive = 500;       ///< keepalive time [ms]
//----------------------------------------------------------------------

// Communication
Transport transport;
//----------------------------------------------------------------------

/**
 * @brief Method that calculates a trajectory value and writes the return value in _trajData->dOutput
 * @param _benchData pointer to test rig data struct
 * @param _trajData pointer to trajectory struct
 */
void fTrajectory(struct Transport::benchData *_benchData, struct Transport::trajData *_trajData) {
    if (_benchData->lTime < _trajData->lStartTime) {
        _trajData->dOutput = _trajData->dStartValue;
    } else {
        if (_benchData->lTime < _trajData->lEndTime) {
            double dM = (_trajData->dEndValue - _trajData->dStartValue) / (_trajData->lEndTime - _trajData->lStartTime);
            double dN = _trajData->dEndValue - dM * _trajData->lEndTime;
            _trajData->dOutput = dM * _benchData->lTime + dN;
        } else {
            _trajData->dOutput = _trajData->dEndValue;
        }
    }
}
//----------------------------------------------------------------------

/**
 * @brief continuous loop. Is called by Timer1 every \ref lDt milliseconds.
 */
void fContLoop() {
    sei();
    if (transport.runExp()) {
        transport._benchData.lTime += lDt;

        fTrajectory(&transport._benchData, &transport._trajData);

        transport.sendData();

        // handle keepalive signal
        if (lKeepalive != 0 && transport._benchData.lTime > transport.keepaliveTime + lKeepalive) {
            transport.reset();
        }
    }
}
//----------------------------------------------------------------------

/**
 * @brief (arduino function)
 * Initializes Transport protocol, the Timer, and the sensors.
 */
void setup() {
    transport.init();

    // initialize Timer
    Timer1.initialize(lDt * 1000);
    Timer1.attachInterrupt(fContLoop);
}
//----------------------------------------------------------------------

/**
 * @brief (arduino function)
 * Main Loop
 */
void loop() {
    transport.run();
}
//----------------------------------------------------------------------
