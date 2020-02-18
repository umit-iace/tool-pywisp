Transport Layer
===============

To handle all communication interfaces for B&R, Raspberry Pi, Arduino, ... on the same way a middle layer is implemented
called `Transport-Layer`. Additionally to this for the data handling the frame based protocol
`MIN-Protocol <https://github.com/min-protocol/min>`_ is used.

Currently only for wired serial connected devices, like Arduino or STMs, the `MIN-Protocol` itself is used.
On devices where a `TCP`-based approach or a wifi serial connection is used, only the frame handling by `MIN` is
applied.

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

The byte array length differs at each device. On `Arduino UNO` the limit is at 50 bytes, because of the intern memory.