#ifndef TCPSERVER_CLASS_H
#define TCPSERVER_CLASS_H
#include <bur/plctypes.h>
#ifdef _DEFAULT_INCLUDES
#include <AsDefault.h>
#endif
#include <AsTCP.h>
#include <AsIOTime.h>
#include "../Comm.h"
#include "../Transport/Frame.h"

/** @file TcpServer.h
 *  @class TcpIpServer
 *  @brief Implementation of a simple TCP Server
 *
 *	The server is initialised and run using the BuR AsTCP library.
 */

class TcpIpServer: public Comm{
	public:
	/** server status enum */
	enum Status
	{
		ERROR = 0xFF,
		STOP = 0,
		BUSY,
		READY
	};
	private:
	const int serverPort;		///< port to be used by the server
	unsigned long serverID;		///< server ID for function blocks

	unsigned long clientIp;		///< IP address of connected client
	unsigned long clientID;		///< client ID for function blocks

	unsigned short tcp_step;		///< step variable for the server state-machine

	Status _status;
	Status _status_sub;

	struct TcpOpen TcpOpen_0;
	struct TcpServer TcpServer_0;
	struct TcpIoctl TcpIoctl_0;
	struct TcpRecv TcpRecv_0;
	struct TcpSend TcpSend_0;
	struct TcpClose TcpClose_0;

	unsigned char outBuffer[2][255 * (MAX_PAYLOAD + 1)];
	unsigned int outBufferLen[2];
	unsigned char currentOutBuf;
	unsigned char inBuffer[255 * (MAX_PAYLOAD + 1)];
	unsigned int inBufferLen;

	Status read();
	Status write();

	Comm *transp;

	public:
	TcpIpServer(int port)
		:serverPort(port),
		status(_status)
	{};

	void deinit();
	void init();
	/** cyclic read/write method */
	void sync();

	void closeSockets();
	/** readonly pointer to server status */
	const Status &status;
	/** Method to queue communication frame */
	void handleFrame(Frame frame);
	/** Method to register the transport protocol instance */
	void registerListener(Comm *transp);
};
#endif //TCPSERVER_CLASS_H
