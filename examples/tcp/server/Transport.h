//
// Created by Jens Wurm on 04.01.19.
//

#ifndef TRANSPORT_H
#define TRANSPORT_H

#include "utils.h"

class Transport {
public:
    bool runExp() { return this->bActivateExperiment; }

    void sendData();

    /**
     * @brief struct of test rig data
     */
    struct benchData {
        unsigned long lTime = 0;                    ///< milliseconds since start of experiment
        bool bReset = false;                        ///< reset flag for new experiment start
    } _benchData;

    bool bActivateExperiment = true;
};


#endif //TRANSPORT_H
