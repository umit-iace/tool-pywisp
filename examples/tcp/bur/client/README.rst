=================================
Visualization for the TCP example
=================================

This `pyWisp` example can be used for the PC and for the B&R example.
The following features are included:

* Remote controls

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
      - unsigned long + 1x byte + 1x long + 1x float + 1x real
      - time + value1 + value2 + value3 + value4
      - from server
      - TestTCP (TestBench)
    * - 11
      - unsigned long + 1x double
      - time + trajectory output
      - from Server
      - RampTrajectory (Trajectory)
    * - 12
      - 1x byte + 1x int + 1x float + 1x double
      - time + value1 + value2 + value3 + value4
      - to Server
      - TestTCP (TestBench)
    * - 13
      - 2x long + 2x double
      - StartValue, StartTime, EndValue, EndTime
      - to Server
      - RampTrajectory (Trajectory)
    * - 14
      - 1x uint, 2x double*
      - series length, time and data series
      - to Server
      - SeriesTrajectory (Trajectory)
    * - 15
      - unsigned long + 1x double
      - time + trajectory output
      - from Server
      - SeriesTrajectory (Trajectory)
