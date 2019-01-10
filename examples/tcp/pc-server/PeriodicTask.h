/** @file PeriodicTask.h
 *
 * Copyright (c) 2018 IACE
 */
#ifndef PERIODIC_H
#define PERIODIC_H

#include <boost/asio.hpp>
#include <boost/bind.hpp>

/**
 *@brief Class, that realizes a periodic task.
 */
class PeriodicTask : boost::noncopyable {
public:
    typedef std::function<void()> handlerFunction;

    PeriodicTask(boost::asio::io_service &ioService, std::string const &name, int interval, handlerFunction task)
            : ioService(ioService), interval(interval), task(task), name(name), timer(ioService) {
        ioService.post(boost::bind(&PeriodicTask::start, this));
    }

    /**
     * @brief Executes the task.
     * @param ec error of the task execution.
     */
    void execute(boost::system::error_code const &ec) {
        if (ec != boost::asio::error::operation_aborted) {
            task();

            timer.expires_at(timer.expires_at() + boost::posix_time::seconds(interval));
            startWait();
        }
    }

    /**
     * @brief Starts the timer of the task.
     */
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
    handlerFunction task;
    std::string name;
    int interval;
};

/**
 * @Brief Class, that realizes a periodic scheduler of different task.
 */
class PeriodicScheduler : boost::noncopyable {
public:
    PeriodicScheduler(boost::asio::io_service &ioService) : ioService(ioService) {

    }

    /**
     * @brief Adds a periodic task. The task is started if the io_context object runs.
     * @param name name of the task.
     * @param task task function, that is processed in task.
     * @param interval time intervall of the periddic task.
     */
    void addTask(std::string const &name, PeriodicTask::handlerFunction const &task, int interval) {
        tasks.push_back(std::make_unique<PeriodicTask>(std::ref(ioService), name, interval, task));
    }

private:
    boost::asio::io_service &ioService;
    std::vector<std::unique_ptr<PeriodicTask>> tasks;
};

#endif //PERIODIC_H
