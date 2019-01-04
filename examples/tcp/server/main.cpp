#include <boost/asio.hpp>
#include <boost/bind.hpp>

#include "PeriodicTask.h"
#include "Transport.h"

const unsigned long lDt = 10;          ///< Sampling step [s]

Transport transport;

void fContLoop() {
    if (transport.runExp()) {
        transport._benchData.lTime += lDt;
        transport.sendData();
    }
}


int main(int argc, char const *argv[])
{
    PeriodicScheduler scheduler;
    scheduler.addTask("fContLoop", boost::bind(fContLoop), 1);

    scheduler.run();

    return 0;
}