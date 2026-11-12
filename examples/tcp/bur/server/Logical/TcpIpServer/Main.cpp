#define _BUR_USE_DECLARATION_IN_IEC
#ifdef _DEFAULT_INCLUDES
	#include "AsDefault.h"
#endif
#include "../Libraries/TcpIp/TcpIpServer.h"
#include "../Libraries/Transport/Transport.h"

/**< amount of memory to be allocated for heap storage must be specified for
     every ANSI C++ program with the bur_heap_size variable */
unsigned long bur_heap_size = 0x1000; /* nothing is allocated with new */

/** TcpIpServer instance */
TcpIpServer Server(50007);

/** Transport instance */
Transport transport;

void _INIT ProgramInit(void)
{
	Server.registerListener(&transport);
	transport.registerServer(&Server);
	Server.deinit();
}

/** runs in Cyclic#4 (100 ms) after ControlLoop */
void _CYCLIC ProgramCyclic(void)
{
	state = Server.run();
	if (!Server.isRun())
		transport.reset();
	/* start, stop, missed heartbeat and disconnect are handled by the server */
	if (Server.started())
		benchData.lTime = 0;
	expData.bActivateExperiment = Server.running();
	/** send data every cycle (100 ms) */
	if (expData.bActivateExperiment) {
		transport.sendData();
		benchData.lTime += 100;
	}
}

void _EXIT ProgramExit(void)
{
	/* TcpClose is asynchronous: close the sockets before the task is removed (bounded, no endless loop) */
	for (unsigned long i = 0; i < 100000 && !Server.close(); ++i)
		;
}
