/** @file TcpServer.h
 *
 * Copyright (c) 2018 IACE
 */
#ifndef TCPSERVER_H
#define TCPSERVER_H

#include <ctime>
#include <iostream>
#include <string>
#include <boost/bind.hpp>
#include <boost/shared_ptr.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/asio.hpp>

/**
 * @brief Tcp connection class to connect a client. Send and receive data from the client. Input and
 * output data is stored in two queues.
 */
class TcpConnection
        : public boost::enable_shared_from_this<TcpConnection> {
public:
    typedef boost::shared_ptr<TcpConnection> pointer;

    static pointer create(boost::asio::io_context &ioContext, Queue<Frame> &inputQueue, Queue<Frame> &outputQueue) {
        return pointer(new TcpConnection(ioContext, inputQueue, outputQueue));
    }

    boost::asio::ip::tcp::socket &socket() {
        return tSocket;
    }

    /**
     * @brief Starts the send and receive loop after client is connected.
     */
    void start() {
        receiveLoop();
        sendLoop();

    }

private:
    TcpConnection(boost::asio::io_context &ioContext, Queue<Frame> &inputQueue, Queue<Frame> &outputQueue)
            : tSocket(ioContext), dlTimer(ioContext), inputQueue(inputQueue), outputQueue(outputQueue) {
    }

    /**
     * @brief Receives asyncronous data from the socket and write it to input queue.
     */
    void receiveLoop() {
        auto This = shared_from_this();
        boost::asio::async_read(tSocket, sBuffer, boost::asio::transfer_exactly(MAX_PAYLOAD + 1),
                                [This, this](boost::system::error_code ec, std::size_t transferred) {
                                    if (ec) {
                                        std::cerr << "Receive error: " << ec.message() << "\n";
                                    } else {
                                        const char *bufPtr = boost::asio::buffer_cast<const char *>(sBuffer.data());
                                        Frame frame;
                                        frame.data.id = (unsigned char) bufPtr++[0];
                                        for (int i = 0; i < MAX_PAYLOAD; i++) {
                                            frame.data.payload[i] = (unsigned char) *bufPtr++;
                                        }
                                        inputQueue.push(frame);
                                        sBuffer.consume(MAX_PAYLOAD + 1);
                                        // chain
                                        receiveLoop();
                                    }
                                });
    }

    /**
     * @brief Sends syncronous data to the socket from the output queue in a 100 ms timer.
     */
    void sendLoop() {
        dlTimer.expires_from_now(boost::posix_time::milliseconds(100));
        auto This = shared_from_this();

        bool writeError = false;

        dlTimer.async_wait([This, this](boost::system::error_code ec) {
            if (!ec) {
                if (!outputQueue.empty()) {
                    Frame frame = outputQueue.pop();
                    const char *px = reinterpret_cast<const char *>(&frame.data);
                    boost::asio::write(tSocket, boost::asio::buffer(px, sizeof(frame.data)), ec);
                }

                if (ec) {
                    std::cerr << "Write error: " << ec.message() << "\n";
                } else {
                    // chain
                    sendLoop();
                }
            }
        });
    }

    boost::asio::ip::tcp::socket tSocket;
    boost::asio::deadline_timer dlTimer;
    boost::asio::streambuf sBuffer;
    Queue<Frame> &inputQueue;
    Queue<Frame> &outputQueue;

};

/**
 * @brief Tcp server class, that realize a Tcp server where clients can connect. Port is specifiable.
 */
class TcpServer {
public:
    TcpServer(boost::asio::io_context &ioContext, Queue<Frame> &inputQueue, Queue<Frame> &outputQueue, short sPort)
            : ioContext(ioContext),
              acceptor_(ioContext, boost::asio::ip::tcp::endpoint(boost::asio::ip::tcp::v4(), sPort)),
              inputQueue(inputQueue),
              outputQueue(outputQueue) {
        startAccept();
    }

private:
    /**
     * @brief Accepts a new client connection.
     */
    void startAccept() {
        TcpConnection::pointer newConnection =
                TcpConnection::create(acceptor_.get_executor().context(), std::ref(inputQueue), std::ref(outputQueue));

        acceptor_.async_accept(newConnection->socket(),
                               boost::bind(&TcpServer::handleAccept, this, newConnection,
                                           boost::asio::placeholders::error));
    }

    /**
     * @brief Handles a client connection.
     */
    void handleAccept(TcpConnection::pointer newConnection,
                      const boost::system::error_code &error) {
        if (!error) {
            newConnection->start();
        }

        startAccept();
    }

    boost::asio::io_context &ioContext;
    boost::asio::ip::tcp::acceptor acceptor_;
    Queue<Frame> &inputQueue;
    Queue<Frame> &outputQueue;
};

#endif //TCPSERVER_H
