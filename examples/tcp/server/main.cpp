#include <boost/asio.hpp>
#include <boost/bind.hpp>
#include <boost/thread.hpp>

#include "PeriodicTask.h"
#include "Transport.h"
#include "TcpServer.h"

const unsigned long lDt = 1;          ///< Sampling step [s]

/**
 * @brief Method that calculates the trajectory value and writes the return value in _trajData->dOutput
 * @param _benchData pointer to test rig data struct
 * @param _trajData pointer to trajectory struct
 */
void fTrajectory(struct Transport::benchData *_benchData, struct Transport::trajData *_trajData)
{
    std::cout << _trajData->dStartValue << std::endl;
    std::cout << _trajData->lStartTime << std::endl;
    std::cout << _trajData->dEndValue << std::endl;
    std::cout << _trajData->lEndTime << std::endl;
    std::cout << _benchData->dValue1 << std::endl;
    std::cout << _benchData->fValue2 << std::endl;
    std::cout << _benchData->iValue3 << std::endl;
    std::cout << _benchData->cValue4 << std::endl;

    if (_benchData->lTime < _trajData->lStartTime)
    {
        _trajData->dOutput = _trajData->dStartValue;
    }
    else
    {
        if (_benchData->lTime < _trajData->lEndTime)
        {
            double dM = (_trajData->dEndValue - _trajData->dStartValue) / (_trajData->lEndTime - _trajData->lStartTime);
            double dN = _trajData->dEndValue - dM * _trajData->lEndTime;
            _trajData->dOutput = dM * _benchData->lTime + dN;
        }
        else
        {
            _trajData->dOutput = _trajData->dEndValue;
        }
    }
}
//----------------------------------------------------------------------

/*
 * @brief
 */
void fContLoop(Transport *transport) {
    transport->handleFrames();

    if (transport->runExp()) {
        transport->_benchData.lTime += lDt;

        fTrajectory(&transport->_benchData, &transport->_trajData);

        transport->sendData();
    }
}
//----------------------------------------------------------------------


int main(int argc, char const *argv[])
{
    Queue<Frame> inputQueue;
    Queue<Frame> outputQueue;

    Transport transport(std::ref(inputQueue), std::ref(outputQueue));

    try
    {
        boost::asio::io_service ioService;

        PeriodicScheduler scheduler(std::ref(ioService));
        scheduler.addTask("fContLoop", boost::bind(fContLoop, &transport), 1);

        TcpServer server(ioService, std::ref(inputQueue), std::ref(outputQueue));

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
//----------------------------------------------------------------------
