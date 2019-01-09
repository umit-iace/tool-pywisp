//
// Created by Jens Wurm on 07.01.19.
//
#include "utils.h"

void logText(std::string const &text) {
    auto t = std::time(nullptr);
    auto tm = *std::localtime(&t);
    std::cout << std::put_time(&tm, "%d-%m-%Y %H-%M-%S") << " " << text << std::endl;
}