# This file is part of pyhard2 - An object-oriented framework for the
# development of instrument drivers.

# Copyright (C) 2012-2014 Mathias Laurin, GPLv3


"""This is where the classes for the device driver development kit are
defined.  Parameters relative to every command are stored in `Command`
(read-only, read-write, or write-only; mnemonic; maximum and minimum
value, for example)

Then, the `Commands` are organized in `Subsystems`.  The `Subsystems`
may be nested, which is useful to organize large drivers or SCPI
drivers.

A `Protocol` may be set on a `Subsystem`.  The `Protocol` will handle
the command, like, for example, formatting and sending a request to the
hardware; parse the results; and send it back.

A simplified UML representation of a driver using the classes in this
module is

.. uml::

   class Command {
     read(node=None): object
     write(value=None, node=None): void
   }
   class Context {
     reader: Command.reader
     writer: Command.writer
     value: object
     node: object
     path: [Subsystem]
   }
   class Subsystem {
     read(Context): object
     write(Context): void
   }
   class Protocol {
     read(Context): object
     write(Context): void
   }
   class CommandCallerProtocol {
     read(Context): object
     write(Context): void
   }
   class ObjectWrapperProtocol {
     object
     read(Context): object
     write(Context): void
   }
   class CommunicationProtocol {
     Socket
     read(Context): object
     write(Context): void
   }
   Command      "1..*"  --* "parent 1"      Subsystem
   (Command, Subsystem) --                  Context
   Subsystem    "0..1"  --* "parent 1"      Subsystem
   Subsystem    "1..*"  --* "parent 1"      Protocol
   Protocol             --* "parent 0..1"   Subsystem
   Protocol             <|--                CommandCallerProtocol
   Protocol             <|--                CommunicationProtocol
   Protocol             <|--                ObjectWrapperProtocol

"""
import logging
import time
from copy import deepcopy as _deepcopy
from functools import partial as _partial
from collections import defaultdict as _defaultdict

try:
    from curses import ascii
except ImportError:
    # Curses does not exist on windows, import local copy.
    import ascii

import sip as _sip
for _type in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    _sip.setapi(_type, 2)
from PyQt4 import QtCore
Signal, Slot = QtCore.pyqtSignal, QtCore.pyqtSlot

import serial

logging.basicConfig()
logger = logging.getLogger("pyhard2")


class HardwareError(Exception):
    """Exception upon error returned from the hardware.
    
    Use this exception for errors documented in the hardware manual."""


class DriverError(IOError):
    """Exception occuring after an error in the software."""


def _identity(*args):
    """A simple identity function."""
    return args[0] if len(args) is 1 else args


class Context(object):

    """Request to pass to a `Protocol`.

    Attributes:
        reader: The value stored in `command.reader`.
        writer: The value stored in `command.writer`.
        value: The value to write, or None.
        node: The node on which to read or write, or None.
        subsystem: The `Subsystem` on which the `command` is defined.
        path ([Subsystem]): The list of subsystem traversed until the
            `Protocol`.

    Methods:
        append(subsystem)
            Append to the path.

    """
    def __init__(self, command, value=None, node=None):
        self._command = command
        self.reader = command.reader
        self.writer = command.writer
        self.value = value
        self.node = node
        self.path = []
        # method
        self.append = self.path.append

    def __repr__(self):
        return "%s(command=%r, value=%r, node=%r)" % (
            self.__class__.__name__, self._command, self.value, self.node)

    @property
    def subsystem(self):
        return self.path[0]


class Access(object):

    """Enum for read-only, read-write, and write-only access.

    Attributes:
        RO, WO, RW

    """
    RO, WO, RW = [".".join(("Access", a)) for a in "RO WO RW".split()]


class Command(QtCore.QObject):

    """Store information related to a `Command`.

    Parameters:
        reader (str or callable): Mnemonic or command to read.
        writer (str or callable, optional): Mnemonic or command to
            write.  Default to `reader`.
        minimum (number, optional): Minimum value used for data
            validation.
        maximum (number, optional): Maximum value used for data
            validation.  Values passed to the parameter exceeding
            `minimum` or `maximum` will be silently coerced to avoid
            hardware errors.
        access (Access.RO, Access.WO, Access.RW)
        rfunc (function, optional): Convert on read.
        wfunc (function, optional): Convert on write.  These functions
            can be used either for type conversion (i.e., str to int) or
            for pretty printing.  Do nothing by default.
        doc: docstring

    Attributes:
        signal (value, node):
            Emit the value returned by `read()` and the node.
        Context (class Context): Nested `Context` class.

    """
    signal = Signal(object, object)
    Context = Context
    """`Context` nested in `Command` to make derivable.

    See :class:`Context`.

    """
    def __init__(self, reader, writer=None,
                 minimum=None, maximum=None, 
                 access=Access.RW,
                 rfunc=None, wfunc=None,
                 doc=None,
                ):
        super(Command, self).__init__()
        self.reader = reader
        self.writer = writer if writer is not None else reader
        self.minimum, self.maximum = minimum, maximum
        self.access = access
        self._rfunc = rfunc if rfunc else _identity
        self._wfunc = wfunc if wfunc else _identity
        self.__doc__ = doc

    def __repr__(self):
        return " ".join(
            txt.strip() for txt in """%s(reader=%r, writer=%r,
            minimum=%r, maximum=%r, access=%r,
            rfunc=%r, wfunc=%r, doc=%r)""".splitlines()) % (
                self.__class__.__name__, self.reader, self.writer,
                self.minimum, self.maximum, self.access,
                self._rfunc, self._wfunc, self.__doc__)

    @Slot()
    def read(self, node=None):
        """Request reading a value from `node`.

        Returns:
            The value.

        Raises:
            DriverError: if trying to read a write-only command.

        """
        if self.access is Access.WO:
            raise DriverError("Read access violation in %r" % self)
        value = self._rfunc(self.parent().read(self.Context(self, node=node)))
        self.signal.emit(value, node)
        return value

    @Slot(object, object)
    def write(self, value=None, node=None):
        """Request writing `value` in `node`.

        Raises:
            DriverError: when writing a read-only command or when the
                value is None for a write-only command.

        """
        if self.access is Access.RO:
            raise DriverError("Write access violation in %r" % self)
        if value is None and self.access is not Access.WO:
            raise DriverError("Must write something in %r" % self)
        self.parent().write(self.Context(self, self._wfunc(value), node=node))


class Subsystem(QtCore.QObject):

    """A logical group of one or more commands."""

    def __init__(self, parent=None):
        super(Subsystem, self).__init__(parent)
        self._protocol = None

    def __repr__(self):
        return "%s(parent=%r)" % (self.__class__.__name__, self.parent())

    def __setattr__(self, name, value):
        """The `subsystem` takes the ownership of `commands`."""
        if isinstance(value, Command):
            if not value.parent():
                value.setParent(self)
        super(Subsystem, self).__setattr__(name, value)

    def protocol(self):
        """Return the protocol if one has been set."""
        return self._protocol

    def setProtocol(self, protocol):
        """Set the protocol to `protocol`."""
        self._protocol = protocol

    def read(self, context):
        """Forward the read request.

        Forward to the request to the `Protocol` if one has been set or
        to the `Subsystem`'s parent otherwise.

        Raises:
            AttributeError: if the Subsystem has neither `parent` nor
               `Protocol`.

        """
        context.append(self)
        try:
            return (self._protocol if self._protocol
                    else self.parent()).read(context)
        except AttributeError:
            if not self._protocol and not self._protocol:
                raise DriverError(" ".join(
                    ("%s does not know what to do with %r,"
                     % (self.__class__.__name__, context),
                     "it has neither parent nor protocol.")))
            else:
                raise

    def write(self, context):
        """Forward the write request.

        Forward the request to the `Protocol` if one has been set or to
        the `Subsystem`'s parent otherwise.

        Raises:
            AttributeError: if the Subsystem has neither `parent` nor
               `Protocol`.

        """
        context.append(self)
        try:
            (self._protocol if self._protocol else self.parent()).write(context)
        except AttributeError:
            if not self._protocol and not self._protocol:
                raise DriverError(" ".join(
                    ("%s does not know what to do with %r,",
                     "it has neither parent nor protocol."
                     % self.__class__.__name__, context)))
            else:
                raise


class Protocol(QtCore.QObject):

    """Protocols should derive this class."""

    def __init__(self, parent=None):
        super(Protocol, self).__init__(parent)

    def read(self, context):
        """Handle the read request."""
        raise NotImplementedError

    def write(self, context):
        """Handle the write request."""
        raise NotImplementedError


class CommandCallerProtocol(Protocol):

    """Handle `Commands` with functions for `reader` and `writer`.

    Example:

        >>> class Handled(object):
        ...
        ...     def __init__(self):
        ...         self._value = 0
        ...
        ...     def get_value(self):
        ...         return self._value
        ...
        ...     def set_value(self, value):
        ...         self._value = value
        ...
        >>> handled = Handled()
        >>> driver = Subsystem()
        >>> driver.measure = Command(handled.get_value, handled.set_value)
        >>> driver.setProtocol(CommandCallerProtocol())
        >>> driver.measure.read()     # read handled._value
        0
        >>> driver.measure.write(10)  # write handled._value = 10
        >>> driver.measure.read()     # read new handled._value
        10
        >>> handled._value  # handled._value has changed
        10

    """
    def __init__(self, parent=None):
        super(CommandCallerProtocol, self).__init__(parent)

    def read(self, context):
        """Return ``context.reader()``."""
        return context.reader()

    def write(self, context):
        """Call ``context.writer(context.value)``."""
        context.writer(context.value)


class ObjectWrapperProtocol(Protocol):

    """Get and set attributes on python objects.

    Args:
        wrapped_obj: The nodes are copies of `wrapped_obj`.

    Note:
        The protocol makes one copy of `wrapped_obj` per node.

    Example:

        >>> class Handled(object):
        ...
        ...     def __init__(self):
        ...         self.value = 0
        ...
        >>> handled = Handled()
        >>> protocol = ObjectWrapperProtocol(handled)
        >>> driver = Subsystem()
        >>> driver.measure = Command("value")  # reader is the attribute name
        >>> driver.setProtocol(protocol)
        >>> driver.measure.read(1)       # read handled.value at node 1
        0
        >>> driver.measure.write(10, 1)  # write handled.value = 10
        >>> driver.measure.read(1)       # read new handled.value
        10
        >>> protocol.node(1).value       # read value directly
        10

    """
    def __init__(self, wrapped_obj, parent=None):
        super(ObjectWrapperProtocol, self).__init__(parent)
        self._nodes = _defaultdict(_partial(_deepcopy, wrapped_obj))

    def node(self, node=None):
        """Return the actual object at `node`."""
        return self._nodes[node]

    def read(self, context):
        """Get the attribute named `context.reader` at `context.node`."""
        return self.node(context.node).__getattribute__(context.reader)

    def write(self, context):
        """Set the attribute named `context.writer` at `context.node`
        to `context.value`."""
        self.node(context.node).__setattr__(context.writer, context.value)


class CommunicationProtocol(Protocol):

    """Protocols that communicate via a socket should derive this class
    and implement the `read()` and `write()` methods.

    """
    def __init__(self, socket, parent=None):
        super(CommunicationProtocol, self).__init__(parent)
        self._socket = socket


def splitlines(txt, sep="\n"):
    """Return a list of the lines in `txt`, breaking at `sep`."""
    def _iterator(_txt):
        if not _txt: raise StopIteration()
        partition = _txt.partition(sep)
        yield "".join(partition[0:2])
        # next line: `yield from` with python 3.4
        for __ in _iterator(partition[2]): yield __
    return [__ for __ in _iterator(txt)]


class TesterSocket(object):

    """A fake socket with canned responses, used for testing.

    Attributes:
        msg (dict): map commands received by the socket to canned
           answers.
        newline: newline character.

    """
    def __init__(self, *args, **kwargs):
        self.msg = {}
        self._buffer = []
        self.newline = "\r\n"

    def write(self, message):
        """Buffer the canned answer for `message`."""
        logger.debug("WRITE %r" % message)
        # should split on self.newline
        self._buffer.extend(splitlines(self.msg[message], self.newline))

    def read(self, n):
        """Return `n` characters from the buffer."""
        line = self.readline()
        ans, line = line[0:n], line[n:]
        if line:
            self._buffer.insert(0, line)
        logger.debug("READ %i %r" % (n, ans))
        return ans

    def readline(self):
        """Return one line in the buffer."""
        try:
            line = self._buffer.pop(0)
        except IndexError:
            logger.debug("Timeout")
            line = ""
        logger.debug("LINE %r" % line)
        return line

    def inWaiting(self):
        """Return True is the buffer is not empty."""
        return True if self._buffer else False


class Serial(serial.Serial):

    """Fix `readline()` in `pyserial`."""

    def __init__(self, port=None, newline="\n", *args, **kwargs):
        super(Serial, self).__init__(port, *args, **kwargs)
        self.newline = newline

    def readline(self):
        """Implement own readline since changing EOL character with `io`
        does not work well.

        """
        _start = time.time()
        if not self.newline:
            return super(Serial, self).readline()
        line = ""
        while not line.endswith(self.newline):
            c = self.read(1)
            if (not c and
                self.timeout and
                time.time() - _start > self.timeout):
                # No time out set, but nothing on the line
                break
            else:
                line += c
        return line
