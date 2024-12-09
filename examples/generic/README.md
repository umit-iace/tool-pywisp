# Tool-Libs server example

This is an example of how a testing rig can be implemented using the tool-libs
framework. The system equations are generated using a sympy c-printer, after
solving the system equations there.

## usage

CMake takes care of generating the equations when necessary.
Make sure you have `ncat` installed (from the `nmap` project) and run
```shell
cmake -S . -B build
cmake --build build --target run
```
then connect through pywisp
