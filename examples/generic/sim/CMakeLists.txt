add_executable(sim sim.cpp)

target_include_directories(sim PUBLIC .
    ../inc
)
target_link_libraries(sim
    tool-libs
    tool-libs-linux
    Eigen3::Eigen
)

add_custom_target(run
    DEPENDS sim
    COMMAND ./sim
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    COMMENT "run simulation"
)
add_custom_target(debug
    DEPENDS sim
    COMMAND gdb ./sim
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    COMMENT "debug simulation using gdb"
)
add_custom_target(grind
    DEPENDS sim
    COMMAND valgrind -s --leak-check=full --track-origins=yes ./sim
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    COMMENT "valgrind simulation"
)
