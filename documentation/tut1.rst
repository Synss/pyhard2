==================================
Tutorial: Writing a pyhard2 driver
==================================

Serial drivers always consist of a list of commands (often `bytes`_ or
`mnemonics`_) and some type of `framing`_.  In short, framing is a way to tell
the hardware controller where the command starts and ends and whether we want to
read or write a value.  They are generally described in different parts of the
hardware manual and are actually independent.  `pyhard2` drivers reflect this in
the way they are organized.  :class:`~pyhard2.driver.Subsystem` instances
organize lists of :class:`~pyhard2.driver.Command` that declare properties like
the mnemonic, whether the command is read-only, the minimum value allowed,
functions to use for pretty-printing, etc.  whereas framing is defined in the
:meth:`read` and :meth:`write` methods of classes deriving from
:class:`~pyhard2.driver.Protocol`.

Minimum required toward a working temperature controller driver
===============================================================

This first tutorial shows how to implement a simple serial driver using a
concrete example: the driver to a Series 982 Watlow temperature controller.

Declaring commands
------------------

We start by declaring the list of commands as it generally does not required any
understanding of the protocol itself but simply to translate the instructions
given in the manual to `pyhard2`.  In the present case, the manual describes the
protocol in form of large tables.  We provide an extract of such a table here,
limiting ourselves to the most relevant elements.

.. table:: Commands as given in the manual

   ====     ============================    ==========  ================
   Name     Description                     Access      Range
   ====     ============================    ==========  ================
   DE1      Derivative Output 1 PID         read-write  0.00 to 9.99 min
   C1       Input 1 Value                   read-only   RL1 to RH1
   C2       Input 2 Value                   read-only   RL2 to RH2
   IT1      Integral for Output 1           read-write  0.00 to 99.99
   PB1      Proportional Band Output 1      read-write  ...
   PWR      Percent Power Present Output    read-only   0 to 100
   SP1      Set Point 1                     read-write  RL1 to RH1
   ====     ============================    ==========  ================

There are actually over 60 commands given so that, even if we limit ourselves to
the 7 commands given above now, we should organize the driver in a meaningful
manner.  That will allow us add other useful commands later as the needs emerge.
We simply organize the commands in the same way as the menus on the hardware
controller.

The DE1, IT1 and PB1 commands that set PID values in the controller are in the
`operation` `pid` menu.  `C1`, `C2`, `PWR`, and `SP1` are not in any menu.  In
`pyhard2`, commands are organized in a :class:`~pyhard2.driver.Subsystem` and
`Subsystems` can be nested.  The hardware controller menus can thus be
represented by `pyhard2`'s `Subsystems` very straightforwardly.  After the
necessary imports::

   import unittest
   import pyhard2.driver as drv
   # We define shortcuts.
   Cmd, Access = drv.Command, drv.Access
   # Access.RW for read-write commands (default),
   # Access.RO for read-only, and Access.WO for write-only.

here is the skeleton of the driver with the most important menus::

   class Series982(drv.Subsystem):

      """Driver to Watlow Series 982 controller."""

      def __init__(self, socket):
         self.operation = drv.Subsystem(self)
         self.operation.pid = drv.Subsystem(self.operation)
         # For the sake of the example:
         self.operation.system = drv.Subsystem(self.operation)
         self.setup = drv.Subsystem(self)
         self.setup.output = drv.Subsystem(self.setup)
         self.setup.global_ = drv.Subsystem(self.setup)
         self.factory = drv.Subsystem(self)
         self.factory.lockout = drv.Subsystem(self.factory)
         self.factory.diagnostic = drv.Subsystem(self.factory)
         self.factory.calibration = drv.Subsystem(self.factory)

.. note::

   The parameter passed to `drv.Subsystem` is its parent `Subsystem` and the
   library relies on properly setting it.

The commands themselves are declared as :class:`~pyhard2.driver.Command` and
take the command name given in the manual (``C1``, ``C2``, etc.) and a series of
**optional** arguments like access (read-only, read-write, or write-only),
minimum and maximum values, conversion functions, etc., such that we can now
complete the driver, now limiting ourselves to the most relevant commands: 

.. literalinclude:: tut1.py
   :pyobject: Series982

Protocol
--------

We should now implement the communication protocol used to read and write
commands to the hardware.  In the present case, we implement the `XON/XOFF`_
protocol described in the manual.  Write commands start with ``?`` and end with
a carriage return ``\r`` and read commands start with ``=`` and end with ``\r``.
Adapted from the manual:

"=" Command Example
   - Master: ``= SP1 50\r`` (Set the setpoint prompt value ``SP1`` to 50.)
   - Remote: ``XOFF`` (byte ``\x13``) (This will be returned once the device
     starts processing.  The master must stay offline.)
   - Remote: ``XON`` (byte ``\x11``) (Processing is done. *Do not send another
     message until this character is received.*)

"?" Command Example
   - Master: ``? SP1\r`` (Request the SP1 prompt value.)
   - Remote: ``XOFF`` (The remote is preparing the response. The master must
     stay offline.)
   - Remote: ``XON 50\r`` (The value is returned and *the master may send
     another message once the* ``\r`` *is received.*)

that can be translated to the short UML sequence diagram:

.. uml::

   group Write
   User     ->  Hardware: "= {mnemonic} {value}\r"
   User     <-- Hardware: XOFF
   User     <-- Hardware: XON
   end

   group Read
   User     ->  Hardware: "? {mnemonic}\r"
   User     <-- Hardware: XOFF
   User     <-- Hardware: XON "{value}\r"
   end

Unit test
~~~~~~~~~

Now that we understand the protocol, we can implement unit tests so that (1) we
can test the driver offline (i.e., without the hardware controller) and (2) we
know when the driver is working.  `Canned responses`_ using
:class:`~pyhard2.driver.TesterSocket` should be enough.  We also do not have to
test every command but just enough to be sure that the protocol is implemented
correctly:


.. literalinclude:: tut1.py
   :pyobject: TestSeries982

Actual implementation
~~~~~~~~~~~~~~~~~~~~~

In `pyhard2`, all the communication with the socket is handled in the
:meth:`read` and :meth:`write` methods of a class deriving
:class:`~pyhard2.driver.Protocol`.  Both methods receive a
:class:`~pyhard2.driver.Context` argument that contains all the necessary
information.  In this particular simple example, we derive
:class:`~pyhard2.driver.CommunicationProtocol`.  The serial socket receives and
returns text.  We use python's `format`_ minilanguage for its readability.

.. literalinclude:: tut1.py
   :pyobject: XonXoffProtocol

.. _bytes: http://en.wikipedia.org/wiki/Byte
.. _`Canned responses`: http://en.wikipedia.org/wiki/Canned_response
.. _format: https://docs.python.org/2/library/string.html#format-string-syntax
.. _framing: http://eli.thegreenplace.net/2009/08/12/framing-in-serial-communications/
.. _mnemonics: http://en.wikipedia.org/wiki/Mnemonic
.. _`XON/XOFF`: http://en.wikipedia.org/wiki/Software_flow_control

Using the driver in the GUI
===========================

We could use this driver directly but installing it in the GUI provided by
`pyhard2` gives us a lot more: threaded communication, data saved periodically,
the ability to program the hardware, and more.  It is also about as trivial as
setting headers in a table!

We need to import the other part of the library::

   import pyhard2.ctrlr as ctrlr
   import pyhard2.driver.virtual as virtual

and to actually fill the `driver table` where every column contains a `command`
from the driver definition and every row contains the reference to a node (one
piece of hardware connected to a serial port.)

.. note::

   If only a single instrument is connected to the serial port, the node may be
   set to ``None`` or 0.

We declare this in a function:

.. literalinclude:: tut1.py
   :pyobject: createController

and start it using standard Qt4:

.. literalinclude:: tut1.py
   :pyobject: main

