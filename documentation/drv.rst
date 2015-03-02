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
... 25
>>> driver.power_supply.voltage.write(10)


:mod:`pyhard2.driver.virtual` Module
------------------------------------

.. automodule:: pyhard2.driver.virtual
   :members:

:mod:`pyhard2.driver.aml` Module
--------------------------------

.. automodule:: pyhard2.driver.aml
   :members:

:mod:`pyhard2.driver.amtron` Module
-----------------------------------

.. automodule:: pyhard2.driver.amtron
   :members:

:mod:`pyhard2.driver.bronkhorst` Module
---------------------------------------

.. automodule:: pyhard2.driver.bronkhorst
   :members:

:mod:`pyhard2.driver.daq` Package
---------------------------------

.. automodule:: pyhard2.driver.daq
   :members:

:mod:`pyhard2.driver.daq.windaq` Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pyhard2.driver.daq.windaq
   :members:

:mod:`pyhard2.driver.daq.lindaq` Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pyhard2.driver.daq.lindaq
   :members:

:mod:`pyhard2.driver.deltaelektronika` Module
---------------------------------------------

.. automodule:: pyhard2.driver.deltaelektronika

:mod:`pyhard2.driver.fluke` Module
----------------------------------

.. automodule:: pyhard2.driver.fluke
   :members:

:mod:`pyhard2.driver.ieee` Package
----------------------------------

.. automodule:: pyhard2.driver.ieee
   :members:

:mod:`pyhard2.driver.ieee.ieee488_1` Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pyhard2.driver.ieee.ieee488_1

:mod:`pyhard2.driver.ieee.ieee488_2` Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pyhard2.driver.ieee.ieee488_2

:mod:`pyhard2.driver.ieee.scpi` Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: pyhard2.driver.ieee.scpi
   :members:

:mod:`pyhard2.driver.peaktech` Module
-------------------------------------

.. automodule:: pyhard2.driver.peaktech
   :members:

:mod:`pyhard2.driver.pfeiffer` Module
-------------------------------------

.. automodule:: pyhard2.driver.pfeiffer
   :members:

:mod:`pyhard2.driver.watlow` Module
-----------------------------------

.. automodule:: pyhard2.driver.watlow
   :members:
