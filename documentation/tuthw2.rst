.. module:: pyhard2.driver


Driver Tutorial 2: Using protocols
==================================


The code from this tutorial is available for download at :download:`tuthw2.py`.


Using protocols is a more flexible approach in most cases and particularly to
drive serial instruments.  Indeed, the manual from the multimeter used in
:doc:`tuthw1` shows that every command sent is terminated with "\\r" and that
the response always starts with the acknowledgement `ack\\r` (where `ack` is
"1" if an error occurred and "0" otherwise).

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
hardware via the serial port.  The `SerialProtocol` class is called with the
argument `fmt_read="{param[getcmd]\\r"`.  This is how framing is done in
pyhard2.  `param[getcmd]` will be replaced with the `getcmd` attribute of the
`Parameter`, that is, "QM" here.

.. note::

   The ``subsys`` mnemonic exists for `Subsystem` attributes and ``instr`` for
   `Instrument` attributes. These can be useful for serialization where the
   subsystems are identified by, e.g., an index or a mnemonic; or daisy-chained
   instruments are identified with their node number.  Moreover, the `fmt_read`
   string uses the `String Formatting Operations` from Python.  Therefore, the
   following strings are valid::

      fmt_read="{subsys[mnemonic]}:{param[getcmd]}?\r"   # SCPI
      fmt_read="{subsys[index]:X}{param[getcmd]}?\r"     # \0xEE\0x12
      fmt_read="{param[getcmd]}{instr[node]:0.2i}\r\n"   # GETD01


Here, "{param[getcmd]}\\r" simply appends the carriage return character "\\r"
to the command.  The optional `fmt_write` argument is used to serialize write
commands.

We also reimplement the `_encode_read` method from the base `SerialProtocol`.
The `_encode_read` from the base class formats the command, sends it to the
hardware and returns the first line of the response, stripped.  We therefore
read it and return the second line of the response instead.

We can complete the driver using this protocol.

.. literalinclude:: tuthw2.py
   :pyobject: parse_response

.. literalinclude:: tuthw2.py
   :pyobject: FlukeSubsystem

Parsing the response from the multimeter is the same as in the previous
tutorial.  We do not need to define `Subsystem.get_measure` anymore since the
communication with the hardware follows the `Protocol`.  Moreover, the first
argument to the `Parameter` is not a function anymore but really the string
that should be sent to the instrument.  This reduces the amount of work
necessary to write complete drivers and potentially reduces the risk of
mistakes.

The `Fluke18x` class itself can be left unchanged although making
`FlukeProtocol` the default is preferable.

.. literalinclude:: tuthw2.py
   :pyobject: Fluke18x

From the point of view of the user, nothing has changed.

>>> serial_port = "COM1"
>>> socket = drv.Serial(serial_port)
>>> with Fluke18x(socket) as multimeter:
...     print("%.1f %s" % (multimeter.measure, multimeter.unit))
...
22.6 Deg C


.. topic:: Protocols

   Whereas the ``getter_func`` keyword argument to `Parameter` handles the
   finer-grained parsing at the command level.  Protocols are used for
   serialization.  They typically handle formatting strings before sending them
   to the hardware and stripping the response from its less relevant parts.


We now have a more flexible way to extend the driver.  Read further about
pyhard2 concepts in :doc:`tuthw3` or go directly to :doc:`tutgui1`.


.. seealso::

   Class :class:`pyhard2.driver.AbstractProtocol`
      API documentation of the `AbstractProtocol` class.

   Class :class:`pyhard2.driver.SerialProtocol`
      API documentation of the `SerialProtocol` class.
