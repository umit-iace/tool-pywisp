/** @file Trajectory.h
 *
 */
#ifndef TRAJECTORY_H
#define TRAJECTORY_H

#include <math.h>

/**
 * @brief Base tractory class.
 */
class Trajectory {
public:
    /**
     * method the computs the trajectory output for the current time
     * @param dTime current time in milliseconds
     * @return trajectory output for the current time
     */
    virtual double compute(const unsigned int &lTime) = 0;
};

/**
 * @brief Class that is derived from the Trajectory class and implements a Ramp trajectory.
 */
class RampTrajectory : public Trajectory {
private:
    unsigned int lStartTime = 0;       ///< value of start time in ms
    double dStartValue = 0.0;           ///< value of start value in ms
    unsigned int lEndTime = 0;         ///< value of final time
    double dEndValue = 0;               ///< value of final value

public:
    /// Constructor of the Ramp trajectory
    RampTrajectory() {}

    /// Destructor of the Ramp trajectory
    ~RampTrajectory() {}

    double compute(const unsigned int &lTime) {
        double dQ = 0;
        if (lTime <= this->lStartTime) {
            dQ = this->dStartValue;
        } else if (lTime >= this->lEndTime) {
            dQ = this->dEndValue;
        } else {
            double dT = this->lEndTime - this->lStartTime;
            double dM = (this->dEndValue - this->dStartValue) / dT;
            double dN =
                    (this->dStartValue * (double) this->lEndTime - this->dEndValue * (double) this->lStartTime) / dT;
            dQ = dM * lTime + dN;
        }

        return dQ;
    };

    void setTimesValues(const unsigned int &lStartTime,
                        const unsigned int &lEndTime,
                        const double &dStartValue,
                        const double &dEndValue) {
        this->lStartTime = lStartTime;
        this->lEndTime = lEndTime;
        this->dStartValue = dStartValue;
        this->dEndValue = dEndValue;
    };

};

/**
 * @brief Class that is derived from the Trajectory class and implements a Polynomial trajectory of order 2.
 */
class SeriesTrajectory : public Trajectory {
private:
    unsigned int iSeriesSize;           ///< length of time series
    unsigned int *lTimes = nullptr;    ///< array of times
    double *dValues = nullptr;          ///< array of values

public:
    /// Constructor of the Polynomial trajectory
    SeriesTrajectory() {}

    /// Destructor of the Polynomial trajectory
    ~SeriesTrajectory() {}

    double compute(const unsigned int &lTime) {
        double dQ = 0;
        if (lTime <= this->lTimes[0]) {
            dQ = this->dValues[0];
        } else if (lTime >= this->lTimes[iSeriesSize - 1]) {
            dQ = this->dValues[iSeriesSize - 1];
        } else {
            for (unsigned int i = 0; i < iSeriesSize - 1; i++) {
                if (this->lTimes[i] <= lTime && lTime <= this->lTimes[i + 1]) {
                    dQ = this->dValues[i];
                    break;
                }
            }
        }

        return dQ;
    };

    void setTime(double dTime, unsigned int iPosition) {
        this->lTimes[iPosition] = (unsigned int) dTime;
    }

    void setValue(const double dValue, unsigned int iPosition) {
        this->dValues[iPosition] = dValue;
    }

    void setSize(const unsigned int iSeriesSize) {
        delete[] this->lTimes;
        delete[] this->dValues;

        this->iSeriesSize = iSeriesSize / 2;

        this->lTimes = new unsigned int[this->iSeriesSize];
        this->dValues = new double[this->iSeriesSize];
    }

    unsigned int getSize() {
        return this->iSeriesSize;
    }

    unsigned int getCompleteSize() {
        return this->iSeriesSize * 2;
    }
};

#endif //TRAJECTORY_H