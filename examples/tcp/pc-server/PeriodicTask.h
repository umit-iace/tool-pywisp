//
// Created by Jens Wurm on 04.01.19.
//

#ifndef PERIODIC_H
#define PERIODIC_H

#include <boost/asio.hpp>
#include <boost/bind.hpp>

class PeriodicTask : boost::noncopyable {
public:
    typedef std::function<void()> handler_fn;

    PeriodicTask(boost::asio::io_service &ioService, std::string const &name, int interval, handler_fn task)
            : ioService(ioService), interval(interval), task(task), name(name), timer(ioService) {
        ioService.post(boost::bind(&PeriodicTask::start, this));
    }

    void execute(boost::system::error_code const &e) {
        if (e != boost::asio::error::operation_aborted) {
            task();

            timer.expires_at(timer.expires_at() + boost::posix_time::seconds(interval));
            startWait();
        }
    }

    void start() {
        task();

        timer.expires_from_now(boost::posix_time::seconds(interval));
        startWait();
    }

private:
    void startWait() {
        timer.async_wait(boost::bind(&PeriodicTask::execute, this, boost::asio::placeholders::error));
    }

private:
    boost::asio::io_service &ioService;
    boost::asio::deadline_timer timer;
    handler_fn task;
    std::string name;
    int interval;
};

class PeriodicScheduler : boost::noncopyable {
public:
    PeriodicScheduler(boost::asio::io_service &ioService) : ioService(ioService) {

    }

    void addTask(std::string const &name, PeriodicTask::handler_fn const &task, int interval) {
        tasks.push_back(std::make_unique<PeriodicTask>(std::ref(ioService), name, interval, task));
    }

private:
    boost::asio::io_service &ioService;
    std::vector<std::unique_ptr<PeriodicTask>> tasks;
};

#endif //PERIODIC_H
