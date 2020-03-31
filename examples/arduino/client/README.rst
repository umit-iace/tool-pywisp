=====================================
Visualization for the Arduino example
=====================================

This `pyWisp` example can be used for the Arduino example.
The following features are included:

* Heartbeat

.. sphinx-marker

Communication
^^^^^^^^^^^^^

For the communication the following frames are used:


.. list-table::
    :widths: 20 20 20 20 20
    :header-rows: 1

    * - ID
      - Datentyp
      - Verwendung
      - Richtung
      - Klasse
    * - 1
      - 1x byte
      - Experiment starten/beenden
      - zum Server
      -
    * - 10
      - unsigned long + 1x byte + 1x long + 1x float + 1x real
      - Zeit + Wert1 + Wert2 + Wert3 + Wert4
      - vom Server
      - TestTCP (TestBench)
    * - 11
      - unsigned long + 1x double
      - Zeit + Traj. Ausgang
      - vom Server
      - RampTrajectory (Trajectory)
    * - 12
      - 1x byte + 1x int + 1x float + 1x double
      - Zeit + Value1 + Value2 + Value3 + Value4
      - zum Server
      - TestTCP (TestBench)
    * - 13
      - 2x long + 2x double
      - StartValue, StartTime, EndValue, EndTime
      - zum Server
      - RampTrajectory (Trajectory)
