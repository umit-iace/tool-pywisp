#ifndef TCPSERVER_CLASS_H
#define TCPSERVER_CLASS_H
#include <bur/plctypes.h>
#ifdef _DEFAULT_INCLUDES
#include <AsDefault.h>
#endif
#include <AsTCP.h>
#include <AsIOTime.h>
#include "../EventLog/EventLog.h"
#include "../Comm.h"

/** \file TCPServer.h
 *  \class TCPServer
 *  \brief Klasse Aufsetzen eines TCP Servers
 *
 *  Über die AsTCP Bibliothek wird der TCP Server initialisiert und ausgeführt.
 *  Die Funktionsblöcke werden als Pointer der Klasse übergeben und im Code
 *  aufgerufen. Zudem wird der Eventlogger verwendet, um evtl. Fehler zu loggen.
 */

/*#define MAX_PAYLOAD (40)
// struct of communication packet
struct frame
{
	unsigned char id;
	unsigned char payload[MAX_PAYLOAD];
};
*/

class TCPServer: public Comm{
	public:
	/** Status definition der Klasse*/
	enum Status
	{
		ERROR = 0xFF,
		STOP = 0,
		BUSY,
		READY
	};
	private:
	/* Variablen für Verbindungsparameter*/
	const int server_port;
	unsigned long ident;
	unsigned long outlen;
	unsigned long client_ip;
	unsigned long client_ident;
	unsigned int client_port;
	unsigned long client_outlen;

	unsigned short tcp_step;
	/* Statusvariablen*/
	Status _status;
	Status _status_sub;
	/* Pointer auf Funktionsblöcke*/
	struct TcpOpen *TcpOpen_0;
	struct TcpServer *TcpServer_0;
	struct TcpIoctl *TcpIoctl_0;
	struct TcpRecv *TcpRecv_0;
	struct TcpSend *TcpSend_0;
	struct TcpClose *TcpClose_0;
	struct tcpLINGER_typ *linger_opt;
	unsigned int linger_opt_len;
	/**< Sende- und Empfangsbuffer mit Längen und cursor*/
	struct frame buffer_out[255];
	unsigned int outc;
	unsigned char buffer_in[255 * (MAX_PAYLOAD + 1)];
	unsigned int recvlength;
	/**< Tcp read und write Funktionen*/
	Status read();
	Status write();
	/**< Eventlogger Pointer*/
	EventLogger *EvLog;

	Comm *transp;

	public:
	TCPServer(int port,
		TcpServer_instances *tcp_inst,
		EventLogger *EvLogger)
		:server_port(port),
		TcpOpen_0(&(tcp_inst->TcpOpen_0)),
		TcpServer_0(&(tcp_inst->TcpServer_0)),
		TcpIoctl_0(&(tcp_inst->TcpIoctl_0)),
		TcpRecv_0(&(tcp_inst->TcpRecv_0)),
		TcpSend_0(&(tcp_inst->TcpSend_0)),
		TcpClose_0(&(tcp_inst->TcpClose_0)),
		linger_opt(&(tcp_inst->linger_opt)),
		linger_opt_len(sizeof(tcp_inst->linger_opt)),
		EvLog(EvLogger),
		status(_status)
	{};
	/**< Initialisierungsmethode*/
	void deinit();
	void init();
	/**< Zyklische Lese- und Schreibmethode*/
	void sync();
	/**< Schließen der Sockets*/
	void close_sockets();
	/**< Readonly methode um Status zu lesen*/
	const Status &status;
	/** Method to queue communication frame */
	void handleFrame(unsigned char id, unsigned char buf[MAX_PAYLOAD]);
	void registerListener(Comm *transp);
};
#endif //TCPSERVER_CLASS_H