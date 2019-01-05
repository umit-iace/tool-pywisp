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
        return socket_;
    }

    void start() {

        message_ = "111234.0";
        boost::asio::async_write(socket_, boost::asio::buffer(message_),
                                 boost::bind(&TcpConnection::handle_write, shared_from_this(),
                                             boost::asio::placeholders::error,
                                             boost::asio::placeholders::bytes_transferred));
    }

private:
    TcpConnection(boost::asio::io_context &ioContext)
            : socket_(ioContext) {
    }

    void handle_write(const boost::system::error_code & /*error*/,
                      size_t /*bytes_transferred*/) {
    }

    boost::asio::ip::tcp::socket socket_;
    std::string message_;
};

class TcpServer {
public:
    TcpServer(boost::asio::io_context &io_context)
            : acceptor_(io_context, boost::asio::ip::tcp::endpoint(boost::asio::ip::tcp::v4(), 50007)) {
        startAccept();
    }

private:
    void startAccept() {
        TcpConnection::pointer newConnection =
                TcpConnection::create(acceptor_.get_executor().context());

        acceptor_.async_accept(newConnection->socket(),
                               boost::bind(&TcpServer::handle_accept, this, newConnection,
                                           boost::asio::placeholders::error));
    }

    void handle_accept(TcpConnection::pointer newConnection,
                       const boost::system::error_code &error) {
        if (!error) {
            // TODO pointer auf threadsafe queue an start übergeben
            newConnection->start();
        }

        startAccept();
    }

    boost::asio::ip::tcp::acceptor acceptor_;
};

#endif //TCPSERVER_H
