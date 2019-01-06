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

    static pointer create(boost::asio::io_context &ioContext) {
        return pointer(new TcpConnection(ioContext));
    }

    boost::asio::ip::tcp::socket &socket() {
        return tSocket;
    }

    void start() {
        receiveLoop();
        sendLoop();

    }

private:
    TcpConnection(boost::asio::io_context &ioContext)
            : tSocket(ioContext), dlTimer(ioContext) {
    }

    std::string _ping = "ping\n";

    void receiveLoop() {
        auto This = shared_from_this();
        boost::asio::async_read_until(tSocket, sBuffer, "\n",
                                      [This, this](boost::system::error_code::error_code ec, size_t) {
                                          if (ec) {
                                              std::cerr << "Receive error: " << ec.message() << "\n";
                                          } else {
                                              std::cout << "Received '" << &sBuffer << "'\n";

                                              // chain
                                              receiveLoop();
                                          }
                                      });
    }

    void sendLoop() {
        dlTimer.expires_from_now(boost::posix_time::seconds(1));
        auto This = shared_from_this();

        dlTimer.async_wait([This, this](boost::system::error_code::error_code ec) {
            if (!ec) {
                boost::asio::async_write(tSocket, boost::asio::buffer(_ping),
                                         [This, this](boost::system::error_code::error_code, size_t) {});

                // chain
                sendLoop();
            }
        });
    }

    boost::asio::ip::tcp::socket tSocket;
    boost::asio::deadline_timer dlTimer;
    boost::asio::streambuf sBuffer;

};

class TcpServer {
public:
    TcpServer(boost::asio::io_context &ioContext)
            : ioContext(ioContext),
              acceptor_(ioContext, boost::asio::ip::tcp::endpoint(boost::asio::ip::tcp::v4(), 50007)) {
        startAccept();
    }

private:
    void startAccept() {
        TcpConnection::pointer newConnection =
                TcpConnection::create(acceptor_.get_executor().context());

        acceptor_.async_accept(newConnection->socket(),
                               boost::bind(&TcpServer::handleAccept, this, newConnection,
                                           boost::asio::placeholders::error));
    }

    void handleAccept(TcpConnection::pointer newConnection,
                      const boost::system::error_code &error) {
        if (!error) {
            // TODO pointer auf threadsafe queue an start übergeben
            newConnection->start();
        }

        startAccept();
    }

    boost::asio::io_context &ioContext;
    boost::asio::ip::tcp::acceptor acceptor_;
};

#endif //TCPSERVER_H
