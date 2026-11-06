include(FetchContent)

if(NOT SIM)
	FetchContent_Declare(stm_cmake
		GIT_REPOSITORY https://github.com/ObKo/stm32-cmake
		GIT_TAG v2.1.0
		GIT_PROGRESS TRUE
	)
	FetchContent_MakeAvailable(stm_cmake)
	set(CMAKE_TOOLCHAIN_FILE ${stm_cmake_SOURCE_DIR}/cmake/stm32_gcc.cmake)
endif()

# the tool-libs version that matches pywisp, TOOL_LIBS_VERSION in pywisp/__init__.py
file(STRINGS ${CMAKE_CURRENT_LIST_DIR}/../../pywisp/__init__.py TOOL_LIBS_VERSION
	REGEX "^TOOL_LIBS_VERSION = ")
string(REGEX REPLACE "^TOOL_LIBS_VERSION = '(.*)'$" "\\1" TOOL_LIBS_VERSION "${TOOL_LIBS_VERSION}")
FetchContent_Declare(tool-libs
	GIT_REPOSITORY https://github.com/umit-iace/tool-libs
	GIT_TAG ${TOOL_LIBS_VERSION}
	GIT_PROGRESS TRUE
)
FetchContent_MakeAvailable(tool-libs)
# no version in find_package: the config of eigen 3.x only accepts 3.x, eigen 5 only 5.x
find_package(Eigen3 REQUIRED NO_MODULE)
if(Eigen3_VERSION VERSION_LESS 3.3)
	message(FATAL_ERROR "Eigen ${Eigen3_VERSION} found, at least 3.3 is required")
endif()
