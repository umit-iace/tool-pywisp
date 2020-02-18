.. _chapter_examples:

Examples
========

In the following sections examples for serial and Tcp/IP communications can be found with a running server and client
for the accordingly system and can be used as starting point for an own implementations. The examples use the same
program at the client and server side. If the experiment is started, a ramp trajectory is simulated and data (double,
float, int, char) is send to the GUI and can be changed by user interaction. All examples are runnable with the enclosed
server implementations.

In the Tcp/IP section an additional example completely in `Python` can be found (Generic). The server simulates a
pendulum with two connected connecting rods on a cart. The user can interact directly with the server by control the
force. The position and the angles of the rods can be visualized by graphs or an animation that represents the physical
test rig.


.. toctree::
  :maxdepth: 1

  serial
  tcp
