#include <boost/asio.hpp>
#include <boost/bind.hpp>
#include <boost/thread.hpp>

#include "PeriodicTask.h"
#include "Transport.h"
#include "TcpServer.h"

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
    try
    {
        boost::asio::io_service ioService;

        PeriodicScheduler scheduler(std::ref(ioService));
        scheduler.addTask("fContLoop", boost::bind(fContLoop), 1);

        TcpServer server(ioService);

        boost::thread_group threads;
        for (int i = 0; i < 2; ++i) {
            threads.create_thread(boost::bind(&boost::asio::io_service::run, &ioService));
        }
        threads.join_all();
    }
    catch (std::exception& e)
    {
        std::cerr << e.what() << std::endl;
    }

    return 0;
}