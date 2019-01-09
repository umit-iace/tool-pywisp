/** @file longpipe.ino
 *
 * Copyright (c) 2018 IACE
 */

// Includes
#include <TimerOne.h>
#include <Adafruit_MAX31865.h>
#include <Adafruit_MAX31855.h>
#include <Adafruit_ADS1015.h>
#include "transport.h"

//\cond false
// Defines
#define RREF      430.0
#define RNOMINAL  100.0

#define TM1       (A2)
#define TM2       (A0)
#define TM3       (A1)
#define TM4       (A3)

#define TW1       (10)
#define TW2       (9)
#define TW3       (8)
#define TW4       (2)

#define TWI1      (3)
#define TWI2      (4)
#define TWI3      (7)
#define TWI4      (5)

#define TAMB      (6)
//\endcond
//----------------------------------------------------------------------

// System parameter
const unsigned long lDt = 50;    ///< Sampling step [ms]
//----------------------------------------------------------------------

// Sensors
//\cond false
// Medium Temperatures
Adafruit_MAX31865 Tm[4] = { Adafruit_MAX31865(TM1),
                            Adafruit_MAX31865(TM2),
                            Adafruit_MAX31865(TM3),
                            Adafruit_MAX31865(TM4)
                          };
// outer Wall Temperatures
Adafruit_MAX31855 Tw[4] = { Adafruit_MAX31855(TW1),
                            Adafruit_MAX31855(TW2),
                            Adafruit_MAX31855(TW3),
                            Adafruit_MAX31855(TW4)
                          };
// inner Wall Temperatures
Adafruit_MAX31855 Twi[4] = {Adafruit_MAX31855(TWI1),
                            Adafruit_MAX31855(TWI2),
                            Adafruit_MAX31855(TWI3),
                            Adafruit_MAX31855(TWI4)
                           };
// ambient Temperature
Adafruit_MAX31855 Tamb = Adafruit_MAX31855(TAMB);

// flow sensor
Adafruit_ADS1115 ads = Adafruit_ADS1115(0x48); // i2c Address

// Thermocouple Offsets
const double dTwOffsetCold[] = {0.807, 0.056, 0.058, 0.893};
const double dTwOffsetHot[] = {0.048, -1.026, -0.913, -0.523};
const double dTwiOffsetCold[] = {-0.046, -0.191, 0.267, -0.637};
const double dTwiOffsetHot[] = {-0.608, -1.015, -0.510, -1.301};
const double dTambOffsetCold = 0.003;
const double dTambOffsetHot = -1.154;
//----------------------------------------------------------------------

// Communication
Transport transport;
//\endcond
//----------------------------------------------------------------------

/**
 * @brief Function for correcting the thermocouple characteristic curve
 * @param temp measured temperature
 * @param offsetCold offset at ~22°C
 * @param offsetHot offset at ~81°C
 * @return corrected temperature
 */
inline double fCorrectOffset(double temp, double offsetCold, double offsetHot)
{
  // cold offsets were measured at 21.75°C
  // hot offsets were measured at ~81.25°C
  return 21.75 - offsetCold + (temp - 21.75) * (81.25 - offsetHot - 21.75 + offsetCold) / (81.25 - 21.75);
}
//----------------------------------------------------------------------

/**
 *  @brief Function for collecting sensor data
 *  @param _benchData pointer to data struct
 */
inline void fMeasureData(struct Transport::benchData *_benchData)
{
  for (int i = 0; i < 4; ++i) {
    _benchData->dTm[i] = Tm[i].temperature(RNOMINAL, RREF);
  }
  
  for (int i = 0; i < 4; ++i) {
    _benchData->dTw[i] = fCorrectOffset(Tw[i].readCelsius(), dTwOffsetCold[i], dTwOffsetHot[i]);
    _benchData->dTwi[i] = fCorrectOffset(Twi[i].readCelsius(), dTwiOffsetCold[i], dTwiOffsetHot[i]);
  }
  
  _benchData->dTamb = fCorrectOffset(Tamb.readCelsius(), dTambOffsetCold, dTambOffsetHot);
  _benchData->dv = ads.getLastConversionResults() * ads.voltsPerBit();
}
//----------------------------------------------------------------------

/**
 * @brief continuous loop. Is called by Timer1 every \ref lDt milliseconds.
 */
void fContLoop()
{
  sei();
  if (transport.runExp())
  {
    fMeasureData(&transport._benchData);
    transport.sendData();
    transport._benchData.lTime += lDt;
  }
}
//----------------------------------------------------------------------

/**
 * @brief (arduino function)
 * Initializes Transport protocol, the Timer, and the sensors.
 */
void setup()
{
  // initialize transport protocol
  transport.init();
  
  // initialize temperature sensors
  for (int i = 0; i < 4; ++i) {
    Tm[i].begin(MAX31865_4WIRE);
  }
  for (int i = 0; i < 4; ++i) {
    Tw[i].begin();
    Twi[i].begin();
  }
  Tamb.begin();
  
  // initialize flowrate sensor
  ads.begin();
  ads.startContinuous_SingleEnded(0);
  
  // initialize Timer
  Timer1.initialize(lDt * 1000);
  Timer1.attachInterrupt(fContLoop);
}
//----------------------------------------------------------------------

/**
 * @brief (arduino function)
 * Main Loop
 */
void loop()
{
  transport.run();
}
//----------------------------------------------------------------------
