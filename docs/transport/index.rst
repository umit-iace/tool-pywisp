Transport Layer
===============

To handle all communication interfaces at B&R, Raspberry Pi, Arduino, ... on the same way a middle layer is implemented
called `Transport-Layer`. Additionally to this for the handling of data a frame based approach is used, that use the
implementation of the `MIN-Protocol` called `MIN-Frame`.

Currently only on serial used devices, like Arduino, the `MIN-Protocol` itself is used. On devices where a `TCP`-based
approach is used, no special protocol is implemented.

Transport Class
---------------

The primary task of the class is to handle the in and output data. The input data is converted from byte array frame
structure to matching data type and sets the program variables. The output data is capsuled in frames by converting the
data in byte arrays and sends out. Additionally to this, on serial used devices, it handles the communication (read and
write operations of serial).

MIN-Frame
---------

Each `MIN-Frame` data has the structure:

.. list-table::
    :widths: 50 50
    :header-rows: 1

    * - ID
      - Payload
    * - unique identifier, packed as one byte
      - data, packed as byte array

The byte array length differs at each device. On `Arduino UNO` the limits is at 50 bytes, because of the intern memory.