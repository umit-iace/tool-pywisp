==============================
Server for the Arduino example
==============================

.. sphinx-marker

Requirements
^^^^^^^^^^^^

For the usage of the Arduino code the following programs are needed:

- Arduino IDE
- Python
- make

Additionally to this the following repository must be cloned:

- `Arduino-Makefile <https://github.com/sudar/Arduino-Makefile>`_

Useage
^^^^^^

In the makefile you have to correct the path to your arduino installation

.. code:: bash

    ARDUINO_DIR   	= <your path>

and to the Arduino-Makefile

.. code:: bash

    include <your path>/Arduino.mk

To compile the code:

.. code:: bash

    make

To upload the code to Arduino:

.. code:: bash

    make upload
