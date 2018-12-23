=====
Guide
=====

To visulize and control a test rig a pywisp-project is needed. Each project must include the following files:

- main.py: Main file to register all needed files and start the visualization.
- defaults.sreg: The definition of all experiments, that would be done.
- connection.py: The implementation of all connection, that are necessary for the test rig.
- visualization.py: All implementations of all visualizer in vtk or mpl.
- Files for the Experioment Modules: One of different files for the implementation of the different modules. It is
  recommended to have one file each module. See examples.

ExperimentModule
~~~~~~~~~~~~~~~~


Connection
~~~~~~~~~~


Visualizer
~~~~~~~~~~

