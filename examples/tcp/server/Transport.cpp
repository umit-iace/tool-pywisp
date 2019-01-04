//
// Created by Jens Wurm on 04.01.19.
//

#include "Transport.h"

void Transport::sendData() {
    logText("Sende Daten:");
    logText(std::to_string(this->_benchData.lTime));
}