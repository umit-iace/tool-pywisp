/** @file Transport.h
 *
 */
#ifndef TRANSPORT_H
#define TRANSPORT_H

#if defined(ARDUINO) && ARDUINO >= 100
#include "Arduino.h"
#else

#include "WProgram.h"

#endif

#define MAX_PAYLOAD                   (20)
#define TRANSPORT_MAX_WINDOW_SIZE     (40U)
#define MIN_MAX_FRAMES                (16)
#define MIN_MAX_FRAME_DATA            (1<<8)
#define BUFLEN                        (64)

#include "Min.h"

/**
 * @brief Layer class for the min protocol communication between the host the micro controller
 */
class Transport {
public:
    Transport() : cMin(MIN_MAX_FRAMES, MIN_MAX_FRAME_DATA, MAX_PAYLOAD, BUFLEN) {

        static Transport *transportObj = this;

        cMin.add_application_function(
                [](uint8_t id, uint8_t *payload, uint8_t len) {
                    transportObj->handleFrame(id, payload, len);
                }
        );
    }

    void init() {
        cMin.initSerial(Serial);
    }

    void run();         ///< must be called periodically, to ensure correct
    ///< functionality of the class

    /**
     * @brief Function for reading activity status of the experiment
     * @return Experiment active
     */
    bool runExp() { return this->bActivateExperiment; }

    /**
     * @brief reset transport layer, whole rig
     */
    void reset() {
        this->bActivateExperiment = 0;
        this->_benchData.lTime = 0;
    }

    /**
     * Handles incoming data frames.
     * @param id frame identifier
     * @param payload frame data as pointer
     * @param payloadLen length of frame data
     */
    void handleFrame(uint8_t id, uint8_t *payload, uint8_t payloadLen);

    /**
     * @brief Function for sending the \ref benchData to the Host
     */
    void sendData();

    /**
     * @brief struct of test rig data
     */
    struct benchData {
        unsigned long lTime = 0;                    ///< seconds since start of experiment
        double dValue1 = 21454.23123;
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
        double dEndValue = 127.34;         ///< end value of the trajectory
        unsigned long lEndTime = 0;        ///< end time of the trajectory
        double dOutput = 85.0;             ///< output value of the trajectory
    } _trajData;

    unsigned long keepaliveTime = 0;

private:
    bool bActivateExperiment = false;
    unsigned char cCursor = 0;
    uint8_t *payload;
    uint8_t payloadSize;

    void startFrame(unsigned char cSize);

    void startFrame(uint8_t *payload);

    void sendFrame(unsigned char id);

    void unpackExp(uint8_t *payload);

    void unpackBenchData(uint8_t *payload);

    void unpackTrajRampData(uint8_t *payload);

    Min cMin;

    /**
     * Adds a double value to payload
    * @param dValue value that is packed in payload
    */
    void pack(double dValue);

    /**
     * Adds an unsigned long value to payload
     * @param lValue value that is packed in payload
     */
    void pack(unsigned long lValue);

    /**
     * Adds a float value to payload
     * @param fValue value that is packed in payload
     */
    void pack(float fValue);

    /**
     * Adds an integer value to payload
     * @param iValue value that is packed in payload
     */
    void pack(int iValue);

    /**
     * Adds an unsigned char value to payload
     * @param cValue value that is packed in payload
     */
    void pack(unsigned char cValue);

    /**
     * Convert a unsigned 32 bit unsigned integer in a byte array
     * @param data the 32 bit integer
     * @param payload byte array
     */
    void pack32(uint32_t data, uint8_t payload[]);

    /**
     * Convert a 4 byte array to a 32 bit unsigned integer
     * @return the 32 bit unsigned integer
     */
    uint32_t unPack32();

    /**
     * Return a double value from payload
     * @param dValue value with unpacked data
     */
    void unPack(double &dValue);

    /**
     * Return an unsigned long value from payload
     * @param lValue value with unpacked data
     */
    void unPack(unsigned long &lValue);

    /**
     * Return a float value from payload
     * @param fValue value with unpacked data
     */
    void unPack(float &fValue);

    /**
     * Return an integer value from payload
     * @param iValue value with unpacked data
     */
    void unPack(int &iValue);

    /**
     * Return an unsigned char value from payload
     * @param cValue value with unpacked data
     */
    void unPack(unsigned char &cValue);

    /**
     * Return a bool value from payload
     * @param bValue value with unpacked data
     */
    void unPack(bool &bValue);

};

/**
 * @brief external instance of the transport layer class must be declared in main
 */
extern Transport transport;

#endif // TRANSPORT_H