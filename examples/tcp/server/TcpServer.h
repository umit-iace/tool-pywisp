//
// Created by Jens Wurm on 05.01.19.
//

#ifndef TCPSERVER_H
#define TCPSERVER_H

#include <ctime>
#include <iostream>
#include <string>
#include <boost/bind.hpp>
#include <boost/shared_ptr.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/asio.hpp>


class TcpConnection
        : public boost::enable_shared_from_this<TcpConnection> {
public:
    typedef boost::shared_ptr<TcpConnection> pointer;

    static pointer create(boost::asio::io_context &ioContext, Queue<Frame> &outputQueue) {
        return pointer(new TcpConnection(ioContext, outputQueue));
    }

    boost::asio::ip::tcp::socket &socket() {
        return tSocket;
    }

    void start() {
        receiveLoop();
        sendLoop();

    }

private:
    TcpConnection(boost::asio::io_context &ioContext, Queue<Frame> &outputQueue)
            : tSocket(ioContext), dlTimer(ioContext), outputQueue(outputQueue) {
    }

    void receiveLoop() {
        auto This = shared_from_this();
        boost::asio::async_read(tSocket, sBuffer, boost::asio::transfer_exactly(MAX_PAYLOAD+1),
                                [This, this](boost::system::error_code ec, std::size_t transferred) {
                                    if (ec) {
                                        std::cerr << "Receive error: " << ec.message() << "\n";
                                    } else {
                                        std::cout << "tt '" << sBuffer.size() << "'\n";
                                        const char *bufPtr = boost::asio::buffer_cast<const char *>(sBuffer.data());
                                        std::cout << "Received '" << (int) bufPtr++[0] << "'\n";
                                        sBuffer.consume(MAX_PAYLOAD+1);
                                        // chain
                                        receiveLoop();
                                    }
                                });
    }

    void sendLoop() {
        dlTimer.expires_from_now(boost::posix_time::milliseconds(100));
        auto This = shared_from_this();

        dlTimer.async_wait([This, this](boost::system::error_code::error_code ec) {
            if (!ec) {
                if (!outputQueue.empty()) {
                    Frame frame = outputQueue.pop();
                    const char *px = reinterpret_cast<const char *>(&frame);
                    boost::asio::async_write(tSocket, boost::asio::buffer(px, sizeof(Frame)),
                                             [This, this](boost::system::error_code::error_code, size_t) {});
                }
                // chain
                sendLoop();
            }
        });
    }

    boost::asio::ip::tcp::socket tSocket;
    boost::asio::deadline_timer dlTimer;
    boost::asio::streambuf sBuffer;
    Queue<Frame> &outputQueue;

};

class TcpServer {
public:
    TcpServer(boost::asio::io_context &ioContext, Queue<Frame> &outputQueue)
            : ioContext(ioContext),
              acceptor_(ioContext, boost::asio::ip::tcp::endpoint(boost::asio::ip::tcp::v4(), 50007)),
              outputQueue(outputQueue) {
        startAccept();
    }

private:
    void startAccept() {
        TcpConnection::pointer newConnection =
                TcpConnection::create(acceptor_.get_executor().context(), std::ref(outputQueue));

        acceptor_.async_accept(newConnection->socket(),
                               boost::bind(&TcpServer::handleAccept, this, newConnection,
                                           boost::asio::placeholders::error));
    }

    void handleAccept(TcpConnection::pointer newConnection,
                      const boost::system::error_code &error) {
        if (!error) {
            newConnection->start();
        }

        startAccept();
    }

    boost::asio::io_context &ioContext;
    boost::asio::ip::tcp::acceptor acceptor_;
    Queue<Frame> &outputQueue;
};

#endif //TCPSERVER_H
