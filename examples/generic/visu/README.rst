=====================================
Visualization for the Generic example
=====================================

This `pyWisp` example can be used for the Generic example.
The following features contains no additonal features.

* Heartbeat
.. sphinx-marker

Communication
^^^^^^^^^^^^^

For the communication the following frames are used:


.. list-table::
    :widths: 20 20 20 20 20
    :header-rows: 1

    * - ID
      - Data type
      - Usage
      - Direction
      - Class
    * - 1
      - 1x byte
      - Start/stop experiment
      - to server
      -
    * - 10
      - 1x byte
      - config
      - to Server
      - DoublePendulum (TestBench)
    * - 15
      - unsigned long + 1x double + 1x double + 1x double + 1x double
      - time + pos + phi1 + phi2 + u
      - from Server
      - DoublePendulum (TestBench)
    * - 20
      - 1x byte + 1x array of double
      - type + times + values
      - to Server
      - Trajectory (Trajectory)
    * - 25
      - unsigned long + 1x double + 1x double
      - time + trajectory output + trajectory derivative output
      - from Server
      - Trajectory (Trajectory)
