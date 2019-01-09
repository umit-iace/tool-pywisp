/** @file transport.h
 *
 * Copyright (c) 2018 IACE
 */
#ifndef TRANSPORT_H
#define TRANSPORT_H

#if defined(ARDUINO) && ARDUINO >= 100
  #include "Arduino.h"
#else
  #include "WProgram.h"
#endif

extern "C" {
    #include <min.h>
}

//\cond false
#define BUFLEN (64) ///< length of serial buffer
//\endcond

/**
 * @brief Layer class for the min protocol communication between the host the micro controller
 */
class Transport
{
    public:
        void init();	///< initialize Transport class
        void run();	    ///< must be called periodically, to ensure correct
			            ///< functionality of the class
        /**
         * @brief Function for reading activity status of the experiment
         * @return Experiment active
         */
        bool runExp() { return this->bActivateExperiment; }
        /**
         * @brief Function for sending the \ref benchData to the Host
         */
        void sendData();
        void handleFrame(uint8_t id, uint8_t *payload, uint8_t len);
        		///< internally used function

        /**
         * @brief struct of test rig data
         */
        struct benchData {
            unsigned long lTime = 0;    ///< milliseconds since start of experiment
            double dTm[4];	            ///< medium Temperature, degrees Celsius
            double dTw[4];	            ///< wall Temperature, degrees Celsius
            double dTwi[4];	            ///< inner wall Temperature, degrees Celsius
            double dTamb = 0.0;	        ///< ambient Temperature, degrees Celsius
            double dv = 0.0;	        ///< flow rate of Medium, Volt (is calcutated into m^3/s on Host)
	    } _benchData;	                ///< instance of test rig data

	//\cond false
    private:
        void unpackExp(uint8_t *buf);

        struct min_context ctx;

        uint8_t serialBuf[BUFLEN];

        bool bActivateExperiment = false;
	//\endcond
};

/**
 * @brief external instance of the transport layer class must be declared in main
 */
extern Transport transport;

#endif // TRANSPORT_H