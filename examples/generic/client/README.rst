=====================================
Visualization for the Generic example
=====================================

This `pyWisp` example can be used for the Arduino example.

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
      - unsigned long + 1x double + 1x double + 1x double + 1x double
      - Zeit + x + phi1 + phi2 + u
      - vom Server
      - TestTCP (TestBench)

