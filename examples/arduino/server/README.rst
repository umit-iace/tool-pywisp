=============================================
Visualisierung für den Longpipe Versuchsstand
=============================================

Zur Nutzung des Arduino-Codes sind die folgenden Programme notwendig:

- Arduino IDE
- Python
- make

Zusätzlich werden die folgenden Repositories benötigt:

- `avrlib <https://github.com/umit-iace/tool-avrlib>`_
- `Arduino-Makefile <https://github.com/sudar/Arduino-Makefile>`_

Nähere Informationen zur Installation entnehmen Sie der Dokumentation.


Benutzung
---------

Es ist zu beachten das nach klonen des Repositories das `makefile` nicht
mehr getrackt werden muss, da jeder Nutzer spezifische Änderungen vornehmen
muss. Zum Abschalten des Trackings muss das folgende ausgeführt werden:

.. code:: bash

    git update-index --assume-unchanged makefile

Falls es notwendig sein sollte Änderungen einzuchecken, kann das Tracking mittels

.. code:: bash

    git update-index --no-assume-unchanged makefile

eingeschaltet werden.
