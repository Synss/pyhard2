

====================
Driver API tutorials
====================

.. module:: pyhard2.driver


1. Simple driver implementation
===============================


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
   

The next section shows a more flexible way to design drivers that applies
particularly well to serial instruments.


.. seealso::

   Class :class:`pyhard2.driver.Instrument`
      API documentation of the `Instrument` class.

   Class :class:`pyhard2.driver.Subsystem`
      API documentation of the `Subsystem` class.

   Class :class:`pyhard2.driver.Parameter`
      API documentation of the `Parameter` class.
      
   Class :class:`pyhard2.driver.Action`
      API documentation of the `Action` class.


2. Using protocols
==================


The code from this tutorial is available for download at :download:`tuthw2.py`.


Using protocols is, in most cases, a more flexible approach.  Indeed, the manual
from the multimeter used above shows that every command sent is terminated with
"\\r" and that the response always starts with the acknowledgement `ack\\r`
(where `ack` is "1" if an error occurred and "0" otherwise).

Protocols are used, for example, for framing (serialization and
parsing---formatting to and from the hardware), to checksum the messages or
check return values.

In the present case, the protocol can be set to always add "\\r" to the
commands sent and to check the `ack` code returned by the multimeter.

::

   import pyhard2.driver as drv

.. literalinclude:: tuthw2.py
   :pyobject: FlukeProtocol


This protocol derives from `SerialProtocol` since we communicate with the
hardware via the serial port.  `SerialProtocol` takes two extra keyword
arguments: `fmt_read` and `fmt_write`.  In our example, we set
`fmt_read="{param[getcmd]\\r"`.  This is how framing is done in pyhard2.
`param[getcmd]` will be replaced with the `getcmd` attribute (the first argument
passed to `Parameter.__init__`), that is, "QM" here.

.. note::

   The ``subsys`` mnemonic exists for `Subsystem` attributes and ``protocol``
   for `Protocol` attributes.  These can be useful for serialization where the
   subsystems are identified by, e.g., an index or a mnemonic; or daisy-chained
   instruments are identified with their node number.  Moreover, the `fmt_read`
   string uses the `String Formatting Operations` from Python.  Therefore, the
   following strings are valid::

      fmt_read="{subsys[mnemonic]}:{param[getcmd]}?\r"   # SCPI
      fmt_read="{subsys[index]:X}{param[getcmd]}?\r"     # \0xEE\0x12
      fmt_read="{param[getcmd]}{protocol[node]:0.2i}\r\n"   # GETD01


Here, "{param[getcmd]}\\r" simply appends the carriage return character "\\r"
to the command.  The optional `fmt_write` argument is used to serialize write
commands.

By default, meth:`SerialProtocol._encode_read` formats the command and sends it
to the hardware.  It then returns the first line of the response, stripped.  We
therefore need to reimplement meth:`SerialProtocol._encode_read` so that the
acknowledgement from the hardware is checked and discarded.

We can complete the driver using this protocol.

.. literalinclude:: tuthw2.py
   :pyobject: parse_response

.. literalinclude:: tuthw2.py
   :pyobject: FlukeSubsystem

Parsing the response from the multimeter is the same as in the previous
tutorial.  We do not need to define `Subsystem.__get_measure` anymore since the
communication with the hardware follows the `Protocol`.  Moreover, the first
argument to the `Parameter` is not a function but really the string that should
be sent to the instrument.  This reduces the amount of work necessary to write
complex drivers and potentially reduces the risk of mistakes.

The `Fluke18x` class itself remains as in the previous tutorial.

.. literalinclude:: tuthw2.py
   :pyobject: Fluke18x

Since the `Instrument` is the only class exposed to the user, nothing has
changed wither from her point of view.

>>> serial_port = "COM1"
>>> socket = drv.Serial(serial_port)
>>> multimeter = Fluke18x(socket)
>>> print multimeter.measure, multimeter.unit
22.6 Deg C


.. topic:: Protocols

   Whereas the ``getter_func`` keyword argument to `Parameter` handles the
   finer-grained parsing at the command level.  Protocols are used for
   serialization.  They typically handle formatting strings before sending them
   to the hardware and stripping the response from its less relevant parts.


We now have a more flexible way to extend the driver.


.. seealso::

   Class :class:`pyhard2.driver.AbstractProtocol`
      API documentation of the `AbstractProtocol` class.

   Class :class:`pyhard2.driver.SerialProtocol`
      API documentation of the `SerialProtocol` class.


3. Parameters and actions
=========================

The code from this tutorial is available for download at :download:`tuthw3.py`.


The manual to the meter introduced above further shows that it is possible to
simulate button presses with commands like "`SF {key code}`", where `{key
code}` is an integer between 10 and 30.  We could define twenty commands "SF
10", "SF 11", etc. or add an ``if 10 <= param.getcmd <= 30`` condition in the
protocol, but that would either be a lot of work or a fragile solution.
Instead, we add these commands using :meth:`Subsystem.add_action_by_name`.  The
completed subsystem now looks like:


.. literalinclude:: tuthw3.py
   :pyobject: FlukeSubsystem

with the rest of the classes defined above.

>>> import pyhard2.driver as drv
>>> from tuthw3 import Fluke18x
>>> multimeter = Fluke18x(drv.Serial())
>>> print(multimeter)
path                                    	  type   	doc
========================================	=========	===
measure                                 	Parameter	None
press_button_Hz                         	Action	None
press_button_auto_hold                  	Action	None
press_button_backlight                  	Action	None
press_button_blue                       	Action	None
press_button_calibration                	Action	None
press_button_cancel                     	Action	None
press_button_down_arrow                 	Action	None
press_button_fast_min_max               	Action	None
press_button_hold                       	Action	None
press_button_logging                    	Action	None
press_button_min_max                    	Action	None
press_button_range                      	Action	None
press_button_rel                        	Action	None
press_button_save                       	Action	None
press_button_setup                      	Action	None
press_button_shift                      	Action	None
press_button_up_arrow                   	Action	None
press_button_wake_up                    	Action	None
unit                                    	Parameter	None


.. topic::  Parameters and Actions

   Interactions with the hardware occur via parameters and actions.

   Parameters
      are `set` or `gotten`.  They usually return a value and are better
      expressed by a noun or a quantity like `temperature`, `setpoint`, `power`
      or `duty_cycle`.

   Actions
      are better expressed with a verb like `reset`, `trigger`, or `clear`.
      They do not return values.


:meth:`Subsystem.add_action_by_name` and :meth:`Subsystem.add_parameter_by_name`
can be used to semi-automatically generate subsystems from various formats like
spreadsheet programs.


.. seealso::

   Class :class:`pyhard2.driver.Parameter`
      API documentation of the `Parameter` class.

   Class :class:`pyhard2.driver.Action`
      API documentation of the `Action` class.


4. Semi-automatic driver generation
===================================


The code from this tutorial is available for download at :download:`tuthw3.py`
and :download:`tuthw4.ods`.


:meth:`Subsystem.add_parameter_by_name` and
:meth:`Subsystem.add_action_by_name` introduced above are very powerful.  They
can be used to write `Subsystems` from outside Python.  Here, we complete our
multimeter driver using a spreadsheet program (like LibreOffice).

The sheet is available for download and looks approximately like the table:

.. table:: FlukeSubsystem

   =========  ==============  =======  =========
   type       name            getcmd   read_only
   =========  ==============  =======  =========
   Parameter  identification  ID           FALSE
   Action     default_setup   DS
   Action     reset           RI
   =========  ==============  =======  =========

The file may be opened using `ezodf <http://pythonhosted.org/ezodf>`_::

   from pyhard2.driver.input import odf
   from tuthw3 import *

   class AutoFluke18x(Fluke18x):

      def __init__(self, socket, async=False):
         super(AutoFluke18x, self).__init__(socket, async)
         protocol = FlukeProtocol(socket, async)
         for name, subsystem in \
               odf.subsystems_factory("tuthw4.ods").iteritems():
            setattr(self, name, subsystem(protocol))


The module `pyhard2.driver.input` contains the mechanics to generate subsystems
from various formats.

Each worksheet in the spreadsheet is read in turn and the header is assumed to
be in the first row.  The other rows contain the parameters and actions of the
subsystem.

>>> meter = AutoFluke18x(drv.Serial())  # that we just created above
>>> meter.main = meter.fluke_subsystem  # set default subsystem

Three new commands have been added as confirmed by:

>>> for line in meter.__str__().splitlines():
...     if not line.startswith("press"):
...         print(line)
...
path                                    	  type   	doc
========================================	=========	===
default_setup                           	Action	None
identification                          	Parameter	None
measure                                 	Parameter	None
reset                                   	Action	None
unit                                    	Parameter	None


This demonstrates the flexibility of pyhard2 and the fact that the largest part
of the code constituting pyhard2 drivers *does not actually need to be coded*.


This series of tutorials demonstrated most of pyhard2's features.  The next
series introduces graphical user interfaces starting with the four lines
necessary to log the measurements from our meter into a GUI.

(Four lines excluding PyQt4 boilerplate code.)


.. seealso::

   Class :class:`pyhard2.driver.Subsystem`
      API documentation of the `Subsystem` class.

