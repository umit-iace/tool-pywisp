======================================
Visualisierung für Test TCP Verbindung
======================================

Es wird das pyWisp-Packet benötigt.

.. sphinx-marker

Kommunikation mit Mikrocontroller
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Zur Kommunikation mit dem Mikrocontroller werden die folgenden Frames verwendet. Jedes Frame wird mittels einer
spezifischen ID markiert.


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
      - Startwert, Startzeit, Endwert, Endzeit
      - zum Server
      - RampTrajectory (Trajectory)

Installation
^^^^^^^^^^^^

Für Benutzer:

.. code-block:: bash

    $ git clone https://github.com/umit-iace/tool-pywisp pywisp
    $ cd pywisp
    $ python setup.py install

Für Entwickler:

.. code-block:: bash

    $ virtualenv pywisp
    $ git clone https://github.com/umit-iace/tool-pywisp pywisp
    $ cd pywisp/
    $ python setup.py develop

