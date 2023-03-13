cmake_minimum_required(VERSION 3.25)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_TRY_COMPILE_TARGET_TYPE "STATIC_LIBRARY")
## dependencies
include(FetchContent)
include(ExternalProject)
include(local.cmake OPTIONAL)

FetchContent_Declare(tool-libs
	GIT_REPOSITORY https://github.com/umit-iace/tool-libs
	GIT_TAG master
	GIT_PROGRESS TRUE
)
FetchContent_MakeAvailable(tool-libs)

## Project declaration
project(server C CXX ASM)

find_package(Eigen3 3.3 REQUIRED NO_MODULE)

add_custom_command(
    OUTPUT ${CMAKE_CURRENT_SOURCE_DIR}/inc/doublependulum.h
    COMMAND python codegen.py 
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/settings.py
            ${CMAKE_CURRENT_SOURCE_DIR}/codegen.py
    VERBATIM
    )

add_executable(${PROJECT_NAME} src/server.cpp
    inc/doublependulum.h)

target_include_directories(${PROJECT_NAME} PUBLIC inc)
target_link_libraries(${PROJECT_NAME}
    tool-libs
    tool-libs-linux
    Eigen3::Eigen)
add_custom_target(run
    DEPENDS ${PROJECT_NAME}
    COMMAND ncat -lkuvv4 127.0.0.1 45670 -c ./${PROJECT_NAME}
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    )
