#define _BUR_USE_DECLARATION_IN_IEC
#ifdef _DEFAULT_INCLUDES
	#include "AsDefault.h"
#endif
#include "../Libraries/TcpIp/TcpIpServer.h"
#include "../Libraries/Transport/Transport.h"

/**< amount of memory to be allocated for heap storage must be specified for
     every ANSI C++ program with the bur_heap_size variable */
unsigned long bur_heap_size = 0xFFFFF; 

int counterClose = 0;

/** TcpIpServer instance */
TcpIpServer Server(50007); 

/** Transport instance */
Transport transport;

void _INIT ProgramInit(void)
{
	mainState = 0;
	counterClose = 0;
	Server.registerListener(&transport);
	transport.registerServer(&Server);
	Server.deinit();
}

void _CYCLIC ProgramCyclic(void)
{
	switch (mainState)
	{
		case 0:
			/** start server and wait for client*/
			Server.init();
			if (Server.status == TcpIpServer::READY)
				mainState = 1;
			else if ((Server.status == TcpIpServer::STOP) || (Server.status == TcpIpServer::ERROR))
				mainState = 255;
			break;
		case 1:
			/** read from and write to client */
			Server.sync();
			if (Server.status == TcpIpServer::READY)
				mainState = 1;
			else if ((Server.status == TcpIpServer::STOP) || (Server.status == TcpIpServer::ERROR))
				mainState = 10;
			break;
		case 10:
			/** end connection*/
			Server.closeSockets();
			if (Server.status == TcpIpServer::READY)
				mainState = 11;
			break;
		case 11:
			/** wait 5 seconds, then restart server */
			if (counterClose++ > 50)
			{
				counterClose = 0;
				mainState = 0;
			}
			break;
		default:
			break;
	}
	/** send data every 100ms */
	if (expData.bActivateExperiment) {
		transport.sendData();
		benchData.lTime += 100;
	}
}

void _EXIT ProgramExit(void)
{
    Server.closeSockets();
}
