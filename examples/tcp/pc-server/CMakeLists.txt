cmake_minimum_required(VERSION 3.9)
project(server)

set(CMAKE_CXX_STANDARD 14)

find_package(Boost 1.66.0 REQUIRED system thread)
if (Boost_FOUND)
    include_directories(${Boost_INCLUDE_DIRS})
    add_executable(server
            main.cpp
            utils.h PeriodicTask.h Transport.cpp Transport.h main.cpp TcpServer.h)
    target_link_libraries(server ${Boost_LIBRARIES})

endif ()

