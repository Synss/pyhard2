Drivers
=======


The `Commands` available in each driver are displayed in blue and the
`Subsystems` are shown in red or black in a tree.  For example, reading
the temperature and setting the voltage with the imaginary driver:

.. graphviz::

   digraph foo {
      rankdir="LR";
      node [shape=none fontsize=10];
      temperature [fontcolor=blue];
      current [fontcolor=blue];
      voltage [fontcolor=blue];
      Driver -> power_supply;
      Driver -> temperature;
      power_supply -> current;
      power_supply -> voltage;
   }

is done with

>>> driver = Driver(socket)
>>> driver.temperature.read()
>>> driver.power_supply.voltage.write(10)


Virtual instrument driver
-------------------------

.. automodule:: pyhard2.driver.virtual
   :members:

AML
---
.. automodule:: pyhard2.driver.aml
   :members:

Amtron
------
.. automodule:: pyhard2.driver.amtron
   :members:

Bronkhorst
----------
.. automodule:: pyhard2.driver.bronkhorst
   :members:

DAQ
---
.. automodule:: pyhard2.driver.daq
   :members:

Fluke
-----
.. automodule:: pyhard2.driver.fluke
   :members:

SCPI
----
.. automodule:: pyhard2.driver.ieee
   :members:

.. automodule:: pyhard2.driver.ieee.ieee488_1

.. automodule:: pyhard2.driver.ieee.ieee488_2

.. automodule:: pyhard2.driver.ieee.scpi
   :members:

Peaktech
--------
.. automodule:: pyhard2.driver.peaktech
   :members:

Pfeiffer
--------
.. automodule:: pyhard2.driver.pfeiffer
   :members:

Watlow
------
.. automodule:: pyhard2.driver.watlow
   :members:

