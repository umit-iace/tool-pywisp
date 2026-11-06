/** @file TcpIpServer.cpp
 *  @brief Implementation of the TcpIpServer Class
 */
#include "TcpIpServer.h"
#include <string.h>

/** writes the lowest n bytes of v little endian to p, as the status frame of tool-libs */
static void putLE(unsigned char *p, unsigned long v, int n)
{
	for (int i = 0; i < n; ++i)
		p[i] = (unsigned char)(v >> (8 * i));
}

TcpIpServer::TcpIpServer(int port) : serverPort(port), linger_opt(init_linger_opt()), state(_state)
{
	this->serverID = 0;
	this->clientID = 0;
	this->_state = INIT;
	this->initStep = 0;
	this->connectStep = 0;
	this->lastStatus = 0;
	this->statusFlags = 0;
	memset(this->clientIp, 0, sizeof(this->clientIp));
	memset(&this->atStart, 0, sizeof(this->atStart));
	memset(&this->atSync, 0, sizeof(this->atSync));
	this->_started = false;
	this->transp = 0;
	this->resetSession();
}

void TcpIpServer::setState(TcpIpServer::State s)
{
	this->_state = s;
}

TcpIpServer::State TcpIpServer::run(void)
{
	switch (this->state)
	{
	case TcpIpServer::INIT:
		/** start server and wait for client*/
		this->init();
		break;
	case TcpIpServer::WAIT:
		this->connect();
		break;
	case TcpIpServer::RUN:
		/** read from and write to client */
		this->sync();
		break;
	case TcpIpServer::DISCONNECT:
		/** end connection*/
		this->disconnect();
		break;
	case TcpIpServer::STOP:
	case TcpIpServer::ERROR:
		/** close all sockets and start again */
		if (this->close())
		{
			this->deinit();
			this->setState(INIT);
		}
		break;
	default:
		break;
	}

	return this->state;
}

bool TcpIpServer::isRun(void)
{
	return this->state == RUN;
}

void TcpIpServer::deinit()
{
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
	this->initStep = 0;
	this->connectStep = 0;
}

/**
 *	@brief initialize server
 */
void TcpIpServer::init()
{
	switch (this->initStep)
	{
	case 0:
		this->clientID = 0;
		/* Open TCP Socket */
		TcpOpen_0.pIfAddr = 0;
		TcpOpen_0.port = this->serverPort;
		TcpOpen_0.options = tcpOPT_REUSEADDR;
		TcpOpen_0.enable = true;
		TcpOpen(&TcpOpen_0);
		if (TcpOpen_0.status == ERR_OK)
		{
			this->serverID = TcpOpen_0.ident;
			this->initStep = 1;
		}
		else if (TcpOpen_0.status != ERR_FUB_BUSY)
		{
			this->setState(ERROR);
		}
		break;
	case 1:
		/* set server options */
		/* these ensure that the connection gets closed directly, without waiting for timeouts */
		/* see BuR AsTCP Help files for more information */
		TcpIoctl_0.ident = this->serverID;
		TcpIoctl_0.ioctl = tcpSO_LINGER_SET;
		TcpIoctl_0.pData = (unsigned long)&this->linger_opt;
		TcpIoctl_0.datalen = sizeof(this->linger_opt);
		TcpIoctl_0.enable = true;
		TcpIoctl(&TcpIoctl_0);
		if (TcpIoctl_0.status == ERR_OK)
		{
			this->initStep = 0;
			this->setState(WAIT);
		}
		else if (TcpIoctl_0.status != ERR_FUB_BUSY)
		{
			this->setState(ERROR);
		}
		break;
	default:
		this->initStep = 0;
		break;
	}
}

void TcpIpServer::connect(void)
{
	switch (this->connectStep)
	{
	case 0:
		/* start server and wait for client */
		TcpServer_0.ident = this->serverID;
		TcpServer_0.backlog = 1;
		TcpServer_0.pIpAddr = (unsigned long)this->clientIp;
		TcpServer_0.enable = true;
		TcpServer(&TcpServer_0);
		if (TcpServer_0.status == ERR_OK)
		{
			this->clientID = TcpServer_0.identclnt;
			this->connectStep = 1;
		}
		else if (TcpServer_0.status != ERR_FUB_BUSY)
		{
			this->setState(ERROR);
		}
		break;
	case 1:
		/* set same options for client */
		TcpIoctl_0.ident = this->clientID;
		TcpIoctl_0.ioctl = tcpSO_LINGER_SET;
		TcpIoctl_0.pData = (unsigned long)&this->linger_opt;
		TcpIoctl_0.datalen = sizeof(this->linger_opt);
		TcpIoctl_0.enable = true;
		TcpIoctl(&TcpIoctl_0);
		if (TcpIoctl_0.status == ERR_OK)
		{
			this->connectStep = 0;
			/* nothing of an earlier client must reach the new one */
			this->resetSession();
			this->setState(RUN);
		}
		else if (TcpIoctl_0.status != ERR_FUB_BUSY)
		{
			this->connectStep = 0;
			this->setState(ERROR);
		}
		break;
	default:
		this->connectStep = 0;
		break;
	}
}

/**
 * @brief reads incoming data from client
 * data gets appended to inBuffer, a partial frame of the last call stays at its front
 */
TcpIpServer::State TcpIpServer::read()
{
	TcpRecv_0.ident = this->clientID;
	TcpRecv_0.pData = (unsigned long)(this->inBuffer + this->inBufferLen);
	TcpRecv_0.datamax = sizeof(this->inBuffer) - this->inBufferLen;
	TcpRecv_0.flags = 0;
	TcpRecv_0.enable = true;
	TcpRecv(&TcpRecv_0);
	/* if instead of switch: the B&R status codes are extern constants, not usable as case labels */
	const unsigned short status = TcpRecv_0.status;
	if (status == ERR_OK)
	{
		/* 0 bytes: client already disconnected */
		if (TcpRecv_0.recvlen == 0)
			return DISCONNECT;
		this->inBufferLen += TcpRecv_0.recvlen;
		return RUN;
	}
	if (status == ERR_FUB_BUSY)
		return BUSY;
	if (status == tcpERR_NO_DATA)
		return RUN;
	if (status == tcpERR_NOT_CONNECTED)
		return DISCONNECT;
	return ERROR;
}

/**
 * @brief write data from the current outBuffer to the client
 */
TcpIpServer::State TcpIpServer::write()
{
	if (!this->leftover)
	{
		if (this->outBufferLen[currentOutBuf] == 0)
		{
			if (this->outBufferLen[!currentOutBuf] == 0)
				return RUN; /* nothing to send */
			currentOutBuf = !currentOutBuf;
		}
		TcpSend_0.pData = (unsigned long)this->outBuffer[currentOutBuf];
		TcpSend_0.datalen = this->outBufferLen[currentOutBuf];
	}
	TcpSend_0.ident = this->clientID;
	TcpSend_0.flags = 0;
	TcpSend_0.enable = true;
	TcpSend(&TcpSend_0);
	const unsigned short status = TcpSend_0.status;
	if (status == tcpERR_NOT_CONNECTED)
		return DISCONNECT;
	if (status == ERR_OK)
	{
		this->leftover = false;
		this->outBufferLen[currentOutBuf] = 0;
		currentOutBuf = !currentOutBuf;
		return RUN;
	}
	if (status == tcpERR_SENTLEN)
	{
		this->leftover = true;
		TcpSend_0.pData += TcpSend_0.sentlen;
		TcpSend_0.datalen -= TcpSend_0.sentlen;
		return BUSY;
	}
	if (status == ERR_FUB_BUSY || status == tcpERR_WOULDBLOCK)
		return BUSY;
	return ERROR;
}

/**
 * @brief writes outgoing frames to the currently unused outBuffer
 */
void TcpIpServer::handleFrame(const Frame &frame)
{
	unsigned char b = !this->currentOutBuf;
	/* prefer dropping frames to dying due to buffer overflows */
	if (this->outBufferLen[b] + MAX_PAYLOAD + 1 > sizeof(this->outBuffer[b]))
		return;
	this->outBuffer[b][this->outBufferLen[b]++] = frame.data.id;
	memcpy(this->outBuffer[b] + this->outBufferLen[b], frame.data.payload, MAX_PAYLOAD);
	this->outBufferLen[b] += MAX_PAYLOAD;
}

/**
 * @brief reads and writes data from and to client
 */
void TcpIpServer::sync()
{
	/* read from client */
	State s = read();
	if (s == DISCONNECT || s == ERROR)
	{
		this->setState(s);
		return;
	}
	/* pass on complete frames, keep a partial one for the next call */
	unsigned int pos = 0;
	while (pos + MAX_PAYLOAD + 1 <= this->inBufferLen)
	{
		Frame frame(this->inBuffer[pos]);
		memcpy(frame.data.payload, this->inBuffer + pos + 1, MAX_PAYLOAD);
		if (frame.data.id == CONTROL_ID)
		{
			this->handleControl(frame);
		}
		else
		{
			/* CRC32 over id, length and payload as pywisp.min.frameCrc */
			const unsigned char len = MAX_PAYLOAD;
			this->rxCrc = crc32(this->rxCrc, &frame.data.id, 1);
			this->rxCrc = crc32(this->rxCrc, &len, 1);
			this->rxCrc = crc32(this->rxCrc, frame.data.payload, MAX_PAYLOAD);
			this->rxCount++;
			if (this->transp)
				this->transp->handleFrame(frame);
		}
		pos += MAX_PAYLOAD + 1;
	}
	this->inBufferLen -= pos;
	memmove(this->inBuffer, this->inBuffer + pos, this->inBufferLen);

	/* heartbeat: stop the experiment and tell pyWisp, as tool-libs Experiment::setHeartbeatTimeout */
	unsigned long now = (unsigned long)clock_ms();
	if (this->_running && now - this->lastHeartbeat > HEARTBEAT_TIMEOUT)
	{
		this->_running = false;
		this->timedOut = true;
		this->timeoutTime = now;
		Frame missed(CONTROL_ID); /* payload 0 */
		this->handleFrame(missed);
	}
	/* pyWisp disconnects on the missed heartbeat, a client that still holds the connection is dead */
	if (this->timedOut && now - this->timeoutTime > HEARTBEAT_TIMEOUT)
	{
		this->setState(DISCONNECT);
		return;
	}
	if (now - this->lastStatus >= STATUS_PERIOD)
		this->sendStatus();

	/* send data to client */
	s = write();
	if (s == DISCONNECT || s == ERROR)
		this->setState(s);
}

/**
 * @brief decodes a control frame of pyWisp (pywisp.min.Control), as tool-libs Experiment::handleFrame:
 * bit 0 start/stop, bit 1 heartbeat, bit 2 (with bit 1) sync followed by the sync id
 */
void TcpIpServer::handleControl(const Frame &frame)
{
	const unsigned char cmd = frame.data.payload[0];
	unsigned long now = (unsigned long)clock_ms();
	if (cmd & 0x04)
	{
		/* sync: confirm the frames since the last control frame at once */
		this->atSync.seq = frame.data.payload[1];
		this->atSync.count = this->rxCount;
		this->atSync.crc = this->rxCrc ^ 0xFFFFFFFFUL;
		this->rxCrc = 0xFFFFFFFFUL;
		this->rxCount = 0;
		this->lastHeartbeat = now;
		this->sendStatus();
	}
	else if (cmd & 0x02)
	{
		this->lastHeartbeat = now;
	}
	else
	{
		if (cmd & 0x01)
		{
			this->atStart.seq++;
			this->atStart.count = this->rxCount;
			this->atStart.crc = this->rxCrc ^ 0xFFFFFFFFUL;
			this->_started = true;
			this->timedOut = false;
			this->lastHeartbeat = now;
		}
		this->rxCrc = 0xFFFFFFFFUL;
		this->rxCount = 0;
		this->_running = (cmd & 0x01) != 0;
		/* pyWisp waits for the status to confirm the start */
		if (this->_running)
			this->sendStatus();
	}
}

/**
 * @brief queues the status frame (pywisp.min.RigStatus, version 1, little endian)
 */
void TcpIpServer::sendStatus()
{
	Frame f(STATUS_ID);
	unsigned char *p = f.data.payload;
	unsigned long now = (unsigned long)clock_ms();
	p[0] = 1;
	p[1] = this->_running ? 1 : 0;
	p[2] = this->statusFlags;
	p[3] = this->atStart.seq;
	putLE(p + 4, this->atStart.count, 2);
	putLE(p + 6, this->atStart.crc, 4);
	putLE(p + 10, now, 4);
	p[14] = this->atSync.seq;
	putLE(p + 15, this->atSync.count, 2);
	putLE(p + 17, this->atSync.crc, 4);
	this->handleFrame(f);
	this->lastStatus = now;
}

/**
 * @brief forgets everything of the last client, stops the experiment
 */
void TcpIpServer::resetSession()
{
	this->outBufferLen[0] = 0;
	this->outBufferLen[1] = 0;
	this->currentOutBuf = 0;
	this->leftover = false;
	this->inBufferLen = 0;
	this->rxCrc = 0xFFFFFFFFUL;
	this->rxCount = 0;
	this->_running = false;
	this->timedOut = false;
	this->timeoutTime = 0;
	this->lastHeartbeat = 0;
}

/**
 * @brief closes a socket, asynchronous: call while it returns ERR_FUB_BUSY, ident is 0 afterwards
 */
unsigned short TcpIpServer::closeSocket(unsigned long &ident)
{
	if (!ident)
		return ERR_OK;
	TcpClose_0.ident = ident;
	TcpClose_0.how = 0;
	TcpClose_0.enable = true;
	TcpClose(&TcpClose_0);
	/* an error leaves nothing to close either */
	if (TcpClose_0.status != ERR_FUB_BUSY)
		ident = 0;
	return TcpClose_0.status;
}

/**
 * @brief closes the client socket upon client disconnect
 */
void TcpIpServer::disconnect()
{
	unsigned short status = this->closeSocket(this->clientID);
	if (status == ERR_FUB_BUSY)
		return;
	this->resetSession();
	/* on errors the server socket is opened again */
	this->setState(status == ERR_OK ? WAIT : ERROR);
}

bool TcpIpServer::close()
{
	if (this->closeSocket(this->clientID) == ERR_FUB_BUSY)
		return false;
	if (this->closeSocket(this->serverID) == ERR_FUB_BUSY)
		return false;
	this->resetSession();
	return true;
}

bool TcpIpServer::started()
{
	bool s = this->_started;
	this->_started = false;
	return s;
}

/**
 * @brief registers transport protocol for handling incoming data
 */
void TcpIpServer::registerListener(Comm *t)
{
	this->transp = t;
}

unsigned long TcpIpServer::crc32(unsigned long crc, const unsigned char *data, unsigned int len)
{
	/* bitwise, reflected polynomial 0xEDB88320: 82 bytes per frame are cheap enough */
	for (unsigned int i = 0; i < len; ++i)
	{
		crc ^= data[i];
		for (int k = 0; k < 8; ++k)
			crc = (crc >> 1) ^ (0xEDB88320UL & (0UL - (crc & 1UL)));
	}
	return crc;
}
