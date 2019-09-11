/** @file Utils.h
 *
 */
#ifndef UTILS_H
#define UTILS_H

#include <ctime>
#include <iostream>
#include <iomanip>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>

//----------------------------------------------------------------------

#define MAX_PAYLOAD (80)                                    ///< maximal data size of frame
#define FRAME_LEN_DOUBLE (MAX_PAYLOAD / sizeof(double))     ///< maximale count of data in frame of type double
#define PORT (50007)                                        ///< tcp port of server
//----------------------------------------------------------------------

/**
 * @brief Class implements a general threadsafe queue.
 */
template<typename T>
class Queue {
public:

    /**
     * Returns the current item from queue.
     * @return the current item
     */
    T pop() {
        std::unique_lock<std::mutex> mlock(mutex_);
        while (queue_.empty()) {
            cond_.wait(mlock);
        }
        auto val = queue_.front();
        queue_.pop();
        return val;
    }

    /**
     * @brief Return the current item to a given item.
     * @param item specific item with last queue item.
     */
    void pop(T &item) {
        std::unique_lock<std::mutex> mlock(mutex_);
        while (queue_.empty()) {
            cond_.wait(mlock);
        }
        item = queue_.front();
        queue_.pop();
    }

    /**
     * Pushs an item to the queue.
     * @param item is pushed in queue.
     */
    void push(const T &item) {
        std::unique_lock<std::mutex> mlock(mutex_);
        queue_.push(item);
        mlock.unlock();
        cond_.notify_one();
    }

    /**
     * Check if queue is empty.
     * @return True if empty, otherwise false.
     */
    bool empty() {
        return queue_.empty();
    }

    Queue() = default;

    Queue(const Queue &) = delete;            // disable copying
    Queue &operator=(const Queue &) = delete; // disable assignment

private:
    std::queue<T> queue_;
    std::mutex mutex_;
    std::condition_variable cond_;
};

#endif
