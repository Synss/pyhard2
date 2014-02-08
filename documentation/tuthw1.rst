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

After the acknowledgement, the multimeter returns a line with:

- an echo of the query,
- the measured value, and
- its unit.

It would be more useful to obtain the measure as a float which implies returning
the unit separately.  This can be achieved with a function like:

.. literalinclude::  tuthw1.py
   :pyobject:  parse_response

We then define a `Subsystem`.  `Subsystems` are meant to organize the commands
sent to the hardware in logical units.  In the present case, we only want to
return `measure` and `unit`.  We thus define the corresponding two `Parameters`.
`Parameters` are defined on the `Subsystem` class and act like python
`properties`.  In this first tutorial, we hard-code the communication with the
multimeter in `__get_measure`.

This gives::

   import pyhard2.driver as drv

.. literalinclude::  tuthw1.py
   :pyobject:  FlukeSubsystem

Note that the `parse_response` function that we defined above is passed to the
`getter_func` arguments of the `Parameters`.  It will be applied just before
returning the value.

Now, we should put this `Subsystem` in an `Instrument`.  The instrument
initializes the socket, sets a protocol, and typically takes an extra `async`
keyword parameter that should defaults to False.

.. literalinclude::  tuthw1.py
   :pyobject:  Fluke18x

We did not implement a protocol so far so that we pass `drv.ProtocolLess` to the
subsystem and we forward it `async` as well.

The driver can now be used:

>>> socket = drv.Serial("COM1")  # must be set to the correct COM-port
>>> multimeter = Fluke18x(socket)
>>> print multimeter.measure, multimeter.unit
22.6 Deg C

.. tip::

   Printing an `Instrument` displays the list of supported commands.

   >>> print(multimeter)
   Instrument Fluke18x
   ===================
   main subsystem
   --------------
   FlukeSubsystem <0x...>
   measure Parameter	None
   unit    Parameter	None


That is all.  We have our first driver.


.. topic::  Subsystems

   Subsystems (classes deriving from :class:`pyhard2.driver.Subsystem`) are
   used to organize and group related commands in the driver.

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
