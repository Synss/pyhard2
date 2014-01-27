.. module:: pyhard2.driver


Driver Tutorial 1: Simple driver implementation
===============================================


The code from this tutorial is available for download at :download:`tuthw1.py`.


We will add logging capabilities to a Fluke Series 187 multimeter.  The manual
gives the following information:

- Serial communication at 9600 Baud, no parity, 8 bits, 1 stop bit.
- Communication follows the diagram:

   .. uml::

      User  ->      Meter: QM
      User  <<--    Meter: ACK
      note right: ACK in {0, 1}; 1 on error
      User  <<--    Meter: QM,{reading}
      note right
         <i>reading</i> is the content
         of the primary display
      end note

This translates to::

   import pyhard2.driver as drv

.. literalinclude::  tuthw1.py
   :pyobject:  FlukeSubsystem


`Subsystems` are meant to help organize commands.  `Parameters` are defined on
the class and act like python `properties`.  `get_measure` returns the second
line of the response form the multimeter, which contains

- an echo of the query
- the measurement, and
- its unit.

It would be more useful to obtain the measure as a float and it is good
practice to return the unit separately.  Among the keyword arguments of
`Parameter`, `getter_func` is a function that is applied just before returning
the value.  This is where we can parse the response of the instrument.  A
function like the following works:

.. literalinclude::  tuthw1.py
   :pyobject:  parse_response


Now, we should put this `Subsystem` in an `Instrument`.  Although it is not
strictly necessary to use inheritance to create instruments since

>>> serial_port = "COM1"
>>> socket = drv.Serial(serial_port)
>>> multimeter = drv.Instrument(socket)
>>> multimeter.socket.timeout = 1.0
>>> multimeter.socket.newline = "\r"
>>> multimeter.main = FlukeSubsystem(multimeter)
>>> multimeter.measure
23.0

works as expected.  It is nevertheless recommended as it allows to initialize
the serial socket in `__init__()` and to import the instrument with ``from
driver.fluke import Fluke18x``. 

.. literalinclude::  tuthw1.py
   :pyobject:  Fluke18x


This driver is already usable.

>>> with Fluke18x(socket) as multimeter:
...     print("%.1f %s" % (multimeter.measure, multimeter.unit))
...
22.6 Deg C

.. tip::

   Printing an `Instrument` displays the list of supported commands.

   >>> print(multimeter)
   path                                    	  type   	doc
   ========================================	=========	===
   measure                                 	Parameter	None
   unit                                    	Parameter	None


That is all.  We have our first driver.


.. topic::  Subsystems

   Subsystems (classes deriving from :class:`pyhard2.driver.Subsystem`) are
   used to organize and group related commands in the driver.  They can be
   nested, although this is not recommended.

   The subsystem called ``main`` can be accessed directly such that, e.g.,

   >>> multimeter.main.measure

   and

   >>> multimeter.measure

   are equivalent.
   

You may now want to learn a more flexible way to design drivers that applies
particularly well to serial instruments in :doc:`tuthw2` or go directly to
:doc:`tutgui1`.


.. seealso::

   Class :class:`pyhard2.driver.Instrument`
      API documentation of the `Instrument` class.

   Class :class:`pyhard2.driver.Subsystem`
      API documentation of the `Subsystem` class.

   Class :class:`pyhard2.driver.Parameter`
      API documentation of the `Parameter` class.
      
   Class :class:`pyhard2.driver.Action`
      API documentation of the `Action` class.
