#include "TCPServer.h"

/** \file TCPServer.cpp
 *  \brief Implementation der TCPServer Klasse
 */
void TCPServer::deinit()
{
	/**< Clearen aller Funktionsblöcke*/
	TcpClose_0.enable = false;
	TcpClose(&TcpClose_0);
	TcpOpen_0.enable = false;
	TcpOpen(&TcpOpen_0);
	TcpServer_0.enable = false;
	TcpServer(&TcpServer_0);
	TcpIoctl_0.enable = false;
	TcpIoctl(&TcpIoctl_0);
	TcpRecv_0.enable = false;
	TcpRecv(&TcpRecv_0);
	TcpSend_0.enable = false;
	TcpSend(&TcpSend_0);
	tcp_step = 0;
}

void TCPServer::init()
{
	this->_status = BUSY;
	switch(tcp_step) {
		case 0:
			deinit();
			tcp_step = 1;
			break;
		case 1:
			/**< Öffnen des Tcp Sockets*/
			TcpOpen_0.pIfAddr = 0; //(unsigned long) this->server_ip;
			TcpOpen_0.port = this->server_port;
			TcpOpen_0.options = tcpOPT_REUSEADDR;
			TcpOpen_0.enable = true;
			TcpOpen(&TcpOpen_0);
			if (TcpOpen_0.status == ERR_OK) {
				this->ident = TcpOpen_0.ident;
				//TcpOpen_0->enable = false;
				tcp_step = 2;
			} else if (TcpOpen_0.status == ERR_FUB_BUSY) {
				// intentionally blank
			} else {
				tcp_step = 0;
				this->_status = ERROR;
			}
			break;
		case 2:
			/**< Nimm Einstellungen vor, siehe Hilfe von AsTCP*/
			/**< Durch diese Einstellung wird die Verbindung direkt abgebrochen ohne Buffer zu leeren*/
			linger_opt.lLinger = 0;
			linger_opt.lOnOff = 1;
            
			TcpIoctl_0.ident = this->ident;
			TcpIoctl_0.ioctl = tcpSO_LINGER_SET;
			TcpIoctl_0.pData = (unsigned long) &this->linger_opt;
			TcpIoctl_0.datalen = this->linger_opt_len;
			TcpIoctl_0.enable = true;
			TcpIoctl(&TcpIoctl_0);
			if (TcpIoctl_0.status == ERR_OK) {
				this->outlen = TcpIoctl_0.outlen;
				//TcpIoctl_0->enable = false;
				tcp_step = 3;
			} else if (TcpIoctl_0.status == ERR_FUB_BUSY) {
				// intentionally blank
			} else {
				tcp_step = 0;
				this->_status = ERROR;
			}
			break;
		case 3:
			/**< Starte den Server und warte auf Client*/
			TcpServer_0.ident = ident;
			TcpServer_0.backlog = 1;
			TcpServer_0.pIpAddr = (unsigned long) this->client_ip;
			TcpServer_0.enable = true;
			TcpServer(&TcpServer_0);
			if (TcpServer_0.status == ERR_OK) {
				this->client_ident = TcpServer_0.identclnt;
				this->client_port = TcpServer_0.portclnt;
				//TcpServer_0->enable = false;
				tcp_step = 4;
			} else if (TcpServer_0.status == ERR_FUB_BUSY) {
				//intentionally blank
			} else {
				tcp_step = 0;
				this->_status = ERROR;
			}
			break;
		case 4:
			/**< Gleiche Einstellungen für Client*/
			TcpIoctl_0.ident = this->client_ident;
			TcpIoctl_0.ioctl = tcpSO_LINGER_SET;
			TcpIoctl_0.pData = (unsigned long) &this->linger_opt;
			TcpIoctl_0.datalen = this->linger_opt_len; // TODO always 0? seems wrong
			TcpIoctl_0.enable = true;
			TcpIoctl(&TcpIoctl_0);
			if (TcpIoctl_0.status == ERR_OK) {
				this->client_outlen = TcpIoctl_0.outlen;
				//TcpIoctl_0->enable = false;
				this->_status = READY;
				tcp_step = 0;
			} else if (TcpIoctl_0.status == ERR_FUB_BUSY) {
				// intentionally blank
			} else {
				tcp_step = 0;
				this->_status = ERROR;
			}
			break;
		default:
			break;
	}
}

TCPServer::Status TCPServer::read()
{
	/**< Lese von Client*/
	TcpRecv_0.ident = this->client_ident;
	TcpRecv_0.pData = (unsigned long) this->buffer_in;
	TcpRecv_0.datamax = sizeof(this->buffer_in);
	TcpRecv_0.flags = 0;
	TcpRecv_0.enable = true;
	TcpRecv(&TcpRecv_0);
	if (TcpRecv_0.status == ERR_OK)
	{
		this->recvlength = TcpRecv_0.recvlen;
		//TcpRecv_0->enable = false;
		if (this->recvlength == 0)
		{
			/**< Client bereits geschlossen*/
			return STOP;
		}
		else
			return READY;
	}
	else if (TcpRecv_0.status == ERR_FUB_BUSY)
		;
	else if (TcpRecv_0.status == tcpERR_NO_DATA)
	{
		/**< Keine Daten empfangen*/
		this->recvlength = 0;
		//TcpRecv_0->enable = false;
		return READY;
	}
	else if (TcpRecv_0.status == tcpERR_NOT_CONNECTED)
	{
		/**< Verbindung wurde getrennt*/
		//TcpRecv_0->enable = false;
		return STOP;
	}
	else
	{       
		return ERROR;
	}
	return BUSY;
}

TCPServer::Status TCPServer::write()
{
	/**< Schreibe Daten an Client*/
	TcpSend_0.ident = client_ident;
	TcpSend_0.pData = (unsigned long) buffer_out;
	TcpSend_0.datalen = (MAX_PAYLOAD + 1) * outc;
	TcpSend_0.flags = 0;
	TcpSend_0.enable = true;
	TcpSend(&TcpSend_0);
	outc = 0;
	if (TcpSend_0.status == ERR_OK)
	{
		//TcpSend_0->enable = false;
		return READY;
	}
	else if (TcpSend_0.status == ERR_FUB_BUSY)
		;
	else if (TcpSend_0.status == tcpERR_NOT_CONNECTED)
	{
		/**< Verbindung wurde getrennt*/
		//TcpSend_0->enable = false;
		return STOP;        
	}
	else
		return ERROR;
	return BUSY;
}

void TCPServer::handleFrame(Frame frame)
{
	this->buffer_out[this->outc].data.id = frame.data.id;
	for (int i = 0; i < MAX_PAYLOAD; ++i) {
		this->buffer_out[this->outc].data.payload[i] =frame.data.payload[i];
	}
	this->outc++;
}
	

void TCPServer::sync()
{
	this->_status = BUSY;
	switch (tcp_step) {
		case 0:
			/**< Lese von Client*/
			this->_status_sub = read();
			switch (this->_status_sub) {
				case READY:
					if (this->recvlength > 0) {
						unsigned char *pointer = buffer_in;
						while (pointer - buffer_in < this->recvlength) {
							Frame frame(pointer++[0]);
							for (int i = 0; i < MAX_PAYLOAD; ++i)
								frame.data.payload[i] = *pointer++;
							this->transp->handleFrame(frame);
						}
						recvlength = 0;
					}
					/**< Sende Daten falls vorhanden*/
					if (this->outc > 0) {
						tcp_step = 1;
					} else {
						tcp_step = 0;
						_status = READY;
					}
					break;
				case BUSY:
					// intentionally blank
					break;
				case STOP:
					tcp_step = 0;
					_status = STOP;
					break;
				default:			
					tcp_step = 0;
					_status = ERROR;
					break;			
			}
			break;
		case 1:
			/**< Schreibe Daten an Client*/
			_status_sub = write();
			switch (_status_sub) {
				case READY:
					tcp_step = 0;
					_status = READY;
					break;	
				case BUSY:
					// intentionally blank
					break;
				case STOP:
					tcp_step = 0;
					_status = STOP;
					break;
				default:
					tcp_step = 0;
					_status = ERROR;
					break;
			}
			break;
		default:
			break;
	}
}

void TCPServer::close_sockets()
{
	_status = BUSY;
	static int tcp_step = 0;
	switch (tcp_step)
	{
		case 0:
			/**< Schließe Client Socket*/
			TcpClose_0.ident = client_ident;
			TcpClose_0.how = 0;
			TcpClose_0.enable = true;
			TcpClose(&TcpClose_0);
			if (TcpClose_0.status == ERR_OK)
			{
				//TcpClose_0->enable = false;
				tcp_step = 1;
			}
			else if (TcpClose_0.status == ERR_FUB_BUSY)
				;
			else
			{
				tcp_step = 255;
				_status = ERROR;
			}
			break;
		case 1:
			/**< Schließe Server*/
			TcpClose_0.ident = ident;
			TcpClose_0.how = 0;
			TcpClose_0.enable = true;
			TcpClose(&TcpClose_0);
			if (TcpClose_0.status == ERR_OK)
			{
				// TcpClose_0->enable = false;
				_status = READY;
				tcp_step = 0;
			}
			else if (TcpClose_0.status == ERR_FUB_BUSY)
				;
			else
			{
				tcp_step = 255;
				_status = ERROR;
			}
			break;
		default:
			break;
	}  
}

void TCPServer::registerListener(Comm *t)
{
	transp = t;
}
