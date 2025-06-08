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

FetchContent_Declare(tool-libs
	GIT_REPOSITORY https://github.com/umit-iace/tool-libs
	GIT_TAG master
	GIT_PROGRESS TRUE
)
FetchContent_MakeAvailable(tool-libs)
