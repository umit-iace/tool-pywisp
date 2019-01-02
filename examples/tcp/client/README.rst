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
      - 1x uint
      - Experiment starten/beenden
      - zum µC
      -
    * - 10
      - unsigned long + 1x byte + 1x long + 1x float + 1x real
      - Zeit + Wert1 + Wert2 + Wert3 + Wert4
      - vom Server
      - TestTCP (TestBench)
    * - 11
      - unsigned long + 1x float
      - Zeit + Traj. Ausgang
      - vom Server
      - ConstTrajectory (Trajectory)
    * - 12
      - 1x byte + 1x long + 1x float + 1x real
      - Zeit +
      - zum Server
      - TestTCP (TestBench)
    * - 13
      - 3x float
      - Startwert, Startzeit, Endwert
      - zum Server
      - ConstTrajectory (Trajectory)

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

