#ifndef TCPSERVER_CLASS_H
#define TCPSERVER_CLASS_H
#include <bur/plctypes.h>
#ifdef _DEFAULT_INCLUDES
#include <AsDefault.h>
#endif
#include <AsTCP.h>
#include <astime.h>
#include "../Comm.h"
#include "../Transport/Frame.h"

/** @file TcpServer.h
 *  @class TcpIpServer
 *  @brief Implementation of a simple TCP Server
 *
 *	The server is initialised and run using the BuR AsTCP library.
 *	It also implements the experiment control of pyWisp like the tool-libs `Experiment`:
 *	control frames (id 1: start, stop, heartbeat, sync) are handled here and not passed to
 *	the transport, a status frame (id 2) is sent periodically. Ids 3..5 are reserved for further system frames.
 */
class TcpIpServer: public Comm{
	public:
	/** server status enum */
	enum State
	{
		ERROR = 0xFF,
		INIT = 0,
		WAIT,
		RUN,
		DISCONNECT,
		STOP,
		BUSY
	};
	/** frame id of the experiment control (pywisp.min.CONTROL_FRAME_ID) */
	static const unsigned char CONTROL_ID = 1;
	/** frame id of the status sent to pyWisp (pywisp.min.STATUS_FRAME_ID) */
	static const unsigned char STATUS_ID = 2;
	/** [ms] period of the status frame, as tool-libs `Experiment::enableStatus` */
	static const unsigned long STATUS_PERIOD = 250;
	/** [ms] the experiment stops without heartbeat for this time, pyWisp's HeartbeatTime must be shorter */
	static const unsigned long HEARTBEAT_TIMEOUT = 1000;
	/** [ms] a client that sends nothing for this time is dropped, pyWisp sends a heartbeat every 500 ms while connected */
	static const unsigned long CLIENT_TIMEOUT = 3000;

	private:
	const int serverPort;		///< port to be used by the server
	unsigned long serverID;		///< server ID for function blocks, 0 if closed
	char clientIp[20];		///< IP address of the connected client as string, written by TcpServer
	unsigned long clientID;		///< client ID for function blocks, 0 if closed

	State _state;
	unsigned char initStep;		///< step of init()
	unsigned char connectStep;	///< step of connect()
	bool leftover;				///< a partially sent buffer is pending

	struct TcpOpen TcpOpen_0;
	struct TcpServer TcpServer_0;
	struct TcpIoctl TcpIoctl_0;
	struct TcpRecv TcpRecv_0;
	struct TcpSend TcpSend_0;
	struct TcpClose TcpClose_0;
	const struct tcpLINGER_typ linger_opt;
	const tcpLINGER_typ init_linger_opt(void) {
		const tcpLINGER_typ l = {1,0};
		return l;
	}

	unsigned char outBuffer[2][255 * (MAX_PAYLOAD + 1)];
	unsigned int outBufferLen[2];
	unsigned char currentOutBuf;
	unsigned char inBuffer[255 * (MAX_PAYLOAD + 1)];
	unsigned int inBufferLen;	///< bytes in inBuffer, a partial frame stays at the front

	/** experiment control and status, see tool-libs core/experiment.h */
	struct Received {
		unsigned char seq;		///< start counter or sync id
		unsigned short count;	///< number of frames
		unsigned long crc;		///< their CRC32
	} atStart, atSync;
	unsigned long rxCrc;		///< running CRC32 (not finalized) of the frames since the last control frame
	unsigned short rxCount;		///< their number
	bool _running;				///< experiment running
	bool _started;				///< start received, cleared by started()
	unsigned long lastHeartbeat;	///< [ms] time of the last heartbeat, sync or start
	unsigned long lastStatus;	///< [ms] time of the last status frame
	unsigned long lastReceived;	///< [ms] time of the last data of the client, or of its connect

	State read();
	State write();
	void handleControl(const Frame &frame);
	void sendStatus();
	void resetSession();
	unsigned short closeSocket(unsigned long &ident);

	void setState(enum State);

	Comm *transp;

	public:
	TcpIpServer(int port);

	void deinit();
	// start server
	void init();
	// wait for client
	void connect();
	/** cyclic read/write method */
	void sync();
	// disconnect from client
	void disconnect();
	/** close client and server socket, call until it returns true */
	bool close();

	// call this regularly
	State run();
	// check status is running
	bool isRun();

	/** experiment started by pyWisp and not stopped, timed out or disconnected */
	bool running() const { return _running && _state == RUN; }
	/** true once after a start command */
	bool started();
	/** status bits of the project sent with the status frame (pyWisp `statusFlags`) */
	unsigned char statusFlags;

	/** readonly pointer to server status */
	const State &state;
	/** Method to queue communication frame */
	void handleFrame(const Frame &frame);
	/** Method to register the transport protocol instance */
	void registerListener(Comm *transp);

	/** CRC32 as zlib's crc32, chained: pass the result of the previous call, ~0 to start, finalize with ~ */
	static unsigned long crc32(unsigned long crc, const unsigned char *data, unsigned int len);
};
#endif //TCPSERVER_CLASS_H
