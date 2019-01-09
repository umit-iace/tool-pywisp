Transport Layer
===============

To handle all communication interfaces at B&R, Raspberry Pi, Arduino, ... on the same way a middle layer is implemented
called `Transport-Layer`. Additionally to this for the handling of data a frame based approach is used, that use the
implementation of the `MIN-Protocol` called `MIN-Frame`.


Transport Class
---------------


MIN-Frame
---------

Each `MIN-Frame` data has the structure

.. list-table::
    :widths: 50 50
    :header-rows: 1

    * - ID
      - Payload
    * - unique identifier, packed as one byte
      - data, packed as byte array

The

.. list-table::
    :widths: 30 30 30
    :header-rows: 1

    * - Protocol
      - ID
      - Payload
    * - TCP
      -
      -
    * - Serial
      -
      -
