=====================================================
PyWisp - Weird visualisation of test bench prototypes
=====================================================

PyWisp stands for *Weird visualisation of test bench prototypes*.

PyWisp is targeted at students and researchers working in control engineering. It helps
to implement and run a communication and visualization for a test bench. Based on PyMoskito GUI
it is easy to use, if you run your simulations in it. It uses the same modular structure
to design a control flow for the test bench.

.. include:: AUTHORS.rst

- Name: Digital_Testsprung

  ConstTrajectory:
   StartValue: 255
   StartTime: 1
   EndValue: 60
   PWM: True
  
  Remote:
   test:
    widgettype: 0
    valueon: 22
    parameter: EndValue
   test2:
    widgettype: 0
    valueon: 0
    parameter: EndValue

  BallInTube: