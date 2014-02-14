# This file is part of pyhard2 - An object-oriented framework for the
# development of instrument drivers.

# Copyright (C) 2012-2013 Mathias Laurin, GPLv3


"""
pyhard2.driver
==============

This module defines the classes and functions that constitute the device driver
development kit.

"""

import os
import types

try:
    from curses import ascii
except ImportError:
    # Curses does not exist on windows, import local copy.
    import ascii

from functools import partial

import sip as _sip
for _type in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    _sip.setapi(_type, 2)
from PyQt4.QtCore import QObject, pyqtSignal
Signal = pyqtSignal

import serial


def identity(*args):
    """ A simple identity function. """
    return args[0] if len(args) is 1 else args


class Serial(serial.Serial):

    """ Fix `readline` in `pyserial`. """

    def __init__(self, port=None, newline="\n", *args, **kwargs):
        super(Serial, self).__init__(port, *args, **kwargs)
        self.newline = newline

    def readline(self):
        """
        Implement own readline since changing EOL character with `io`
        does not work well.

        """
        if not self.newline:
            return super(Serial, self).readline()
        line = ""
        while not line.endswith(self.newline):
            c = self.read(1)
            if not c:
                # Timed out
                break
            else:
                line += c
        return line


class SignalProxy(QObject):
    """
    A proxy class for Qt4 signals.

    A SignalProxy can be used in place of a Signal in classes that do
    not inherit QObject.

    """

    signal = Signal(object)

    def __init__(self):
        QObject.__init__(self)
        self.connect = self.signal.connect
        self.disconnect = self.signal.disconnect
        self.emit = self.signal.emit


class TestSocketBase(object):

    """
    Loopback socket to test drivers without hardware.

    Parameters
    ----------
    msg : dict
        Map formatted commands to actual answers from the hardware.
    port : str, optional
    newline : newline character

    Notes
    -----
    Derive this class to implement virtual instruments used to test the
    drivers without the hardware.

    """

    def __init__(self, msg, port=None, newline="\n"):
        self.msg = msg
        self.port = port
        self.newline = newline
        self.cmd = ""

    def __repr__(self):
        return "%s(msg=%r, port=%r, newline=%r)" % (
            self.__class__.__name__, self.msg, self.port, self.newline)

    def write(self, cmd):
        """Fake write by memoizing answer corresponding to command sent.
        """
        self.cmd = self.msg[cmd]

    def read(self, n=0):
        """Fake reads by returning `n` bytes from the answer."""
        c, self.cmd = self.cmd[:n], self.cmd[n:]
        return c

    def readline(self):
        """Fake readline by returning characters from the answer up to
           `newline`."""
        line = ""
        while not line.endswith(self.newline):
            c = self.read(1)
            if not c:
                break
            else:
                line += c
        return line


class HardwareError(Exception):
    """ Exception upon error returned from the hardware. """


class DriverError(IOError):
    """ Exception occuring after an error in the software. """


class Action(object):

    """
    Class for action-type parameters.

    Parameters
    ----------
    getcmd :
        Get the command.
    getter_func : function, optional
        Apply to the value returned by the hardware.
    doc : docstring, optional

    Notes
    -----
    Implements :meth:`__call__`.

    """

    def __init__(self, getcmd, getter_func=None, doc=None):
        self.getcmd = getcmd
        self.getter_func = identity if getter_func is None else getter_func
        self.__doc__ = doc

    def __repr__(self):
        return "%s(getcmd=%r, getter_func=%r, doc=%r)" % (
            self.__class__.__name__,
            self.getcmd, self.getter_func, self.__doc__)

    def __call__(self, subsys):
        """Request action to hardware, does not return."""
        self._get(subsys)

    def __get__(self, subsys, cls=None):
        """This is where the magic happens."""
        return partial(self.__call__, subsys)

    def _get(self, subsys):
        return self.getter_func(
            subsys.protocol._encode_read(subsys, self))


class Parameter(object):

    """
    Descriptor for read-only and read-write parameters.

    Parameters
    ----------
    getcmd : str or callable
        Command to query the parameter.
    setcmd : str or callable, optional
        Command to set the parameter.  If omitted, defaults to `getcmd`.
    minimum, maximum : number, optional
        Minimum and maximum value used for data validation.  Values
        passed to the parameter exceeding `minimum` or `maximum` will be
        silently coerced to avoid hardware errors.
    read_only : bool
        If read_only is True, the paramter will raise an AttributeError
        if one attempts to set its value.
    getter_func, setter_func : function, optional
        These functions can be used either for type conversion (i.e.,
        str to int) or for pretty printing.  Default to :func:`identity`
        if unset.
    doc : docstring

    Notes
    -----

    Implements :meth:`__get__` and :meth:`__set__`.

    """

    def __init__(self, getcmd, setcmd=None,
                 minimum=None, maximum=None, 
                 read_only=False,
                 getter_func=None, setter_func=None,
                 doc=None,
                ):
        self.getcmd = getcmd
        self.setcmd = setcmd if setcmd is not None else getcmd
        self.minimum, self.maximum = minimum, maximum
        self.read_only = read_only
        self.getter_func = identity if getter_func is None else getter_func
        self.setter_func = identity if setter_func is None else setter_func
        self.__doc__ = doc

    def __repr__(self):
        return " ".join(txt.strip() for txt in 
                        """%s(getcmd=%r, setcmd=%r,
                              minimum=%r, maximum=%r,
                              read_only=%r,
                              getter_func=%r, setter_func=%r,
                              doc=%r)""".splitlines()) % (
                                  self.__class__.__name__,
                                  self.getcmd, self.setcmd,
                                  self.minimum, self.maximum,
                                  self.read_only,
                                  self.getter_func, self.setter_func,
                                  self.__doc__)

    def _get(self, subsys):
        value = self.getter_func(subsys.protocol._encode_read(subsys, self))
        subsys._signals.setdefault(self, SignalProxy()).emit(value)
        if not subsys.protocol.async:
            return value

    def _set(self, subsys, val):
        if self.read_only:
            raise AttributeError("Property %s is read only" % self)
        elif self.minimum is not None:
            val = self.minimum if val < self.minimum else val
        elif self.maximum is not None:
            val = self.maximum if val > self.maximum else val
        return subsys.protocol._encode_write(
            subsys, self, self.setter_func(val))
    
    def __get__(self, subsys, cls=None):
        """
        Parameters
        ----------
        subsys : Subsystem
        """
        return self._get(subsys) if subsys is not None else self

    def __set__(self, subsys, val):
        """
        Parameters
        ----------
        subsys : Subsystem
        val :
            Value to set.
        """
        self._set(subsys, val)


class AbstractProtocol(object):

    """
    New Protocols should inherit this class.

    Parameters
    ----------
    socket :
        The socket used to communicate with the driver.
    async : bool
        Whether communication should be synchronous/blocking or
        asynchronous/non-blocking.  Blocking should be preferred when 
        the driver is used interactively and non-blocking, when used in
        a GUI.

    Notes
    -----
    Derived classes need to implement, at least, :meth:`_encode_read`
    for read-only hardware drivers, :meth:`_encode_write` for write-only
    drivers, or both for read-write drivers.

    """
    def __init__(self, socket, async):
        self.socket = socket
        self.async = async

    def __repr__(self):
        return "%s(socket=%r, async=%r)" % (
            self.__class__.__name__, self.socket, self.async)

    def _encode_read(self, subsys, param):
        """`Abstract method` Format and send command to socket."""
        raise NotImplementedError

    def _encode_write(self, subsys, param, val):
        """`Abstract method` Format and send command to socket."""
        raise NotImplementedError


class WrapperProtocol(AbstractProtocol):

    """
    Protocol that makes `wrapped_obj`'s attributes accessible in its
    parent Subsystem.

    Examples
    --------
    >>> class MyClass(object):
    ...
    ...    def __init__(self):
    ...        self.attr = "Some value"
    ...
    >>> class MySubsystem(Subsystem):
    ...
    ...    def __init__(self, obj):
    ...        self.__wrapped = obj
    ...        protocol = WrapperProtocol(self.__wrapped, async=False)
    ...        super(MySubsystem, self).__init__(protocol)
    ...
    ...    my_parameter = Parameter("attr", doc="Accessor to obj.attr")
    ...
    >>> wrapped = MyClass()
    >>> subsys = MySubsystem(wrapped)
    >>> subsys.my_parameter
    'Some value'
    >>> subsys.my_parameter = "Another value"
    >>> wrapped.attr
    'Another value'

    """
    def __init__(self, wrapped_obj, async):
        super(WrapperProtocol, self).__init__(socket=None, async=async)
        self._wrapped_obj = wrapped_obj

    def __repr__(self):
        return "%s(wrapped_obj=%r, async=%r)" % (
            self.__class__.__name__, self._wrapped_obj, self.async)

    def _encode_read(self, subsys, param):
        return self._wrapped_obj.__getattribute__(param.getcmd)

    def _encode_write(self, subsys, param, val):
        self._wrapped_obj.__setattr__(param.setcmd, val)


class ProtocolLess(AbstractProtocol):

    """
    Protocol that lets Actions and Paramters work like python
    properties.

    This protocol should be used whenever framing is not needed.
    Parameters and Actions in a Subsystem that uses `ProtocolLess` take
    function objects as arguments to `getcmd` and `setcmd`, like Python
    properties.

    Examples
    --------
    >>> class MySubsystem(Subsystem):
    ...
    ...    def __init__(self):
    ...        protocol = ProtocolLess(Serial(), async=False)
    ...        super(MySubsystem, self).__init__(protocol)
    ...        self._value = "A value"
    ...
    ...    def __get_value(self):
    ...        return self._value
    ...
    ...    def __set_value(self, value):
    ...        self._value = value
    ...
    ...    value = Parameter(__get_value, __set_value, doc="Accessor")
    ...
    >>> subsys = MySubsystem()
    >>> subsys.value
    'A value'
    >>> subsys.value = "Another value"
    >>> subsys.value
    'Another value'
    >>> print(subsys._value)
    Another value

    """
    def __init__(self, socket, async):
        super(ProtocolLess, self).__init__(socket, async)

    def _encode_read(self, subsys, param):
        return param.getcmd(subsys)

    def _encode_write(self, subsys, param, val):
        param.setcmd(subsys, val)


class SerialProtocol(AbstractProtocol):

    """
    Protocol for serial communication with the hardware.

    Parameters
    ----------
    socket : Serial
    async : bool
    fmt_read : str
        String with placeholders to format read command.  The mnemonics
        `subsys`, `protocol`, and `param` can be used to access
        attributes in the parent Subsystem, its Protocol or the calling
        Parameter (or Action).  The attribute itself is written between
        [] after the mnemonic.  For example:
        ``{subsys[mnemonic]}:{param[getcmd]}?\\r``,
        ``{subsys[index]:X}{param[getcmd]}?\\r``, or
        ``{param[getcmd]}{protocol[node]:0.2i}\\r\\n`` are valid
        arguments.
    fmt_write : str, optional
        string with placeholders to format write command.  See
        documentation to `fmt_read`.  The parameter may be omitted in
        read-only protocols.

    """
    def __init__(self, socket, async, fmt_read=None, fmt_write=None):
        super(SerialProtocol, self).__init__(socket, async)
        self.fmt_read = fmt_read
        self.fmt_write = fmt_write

    def __repr__(self):
        return "%s(socket=%r, async=%r, fmt_read=%r, fmt_write=%r)" % (
            self.__class__.__name__, self.socket, self.async,
            self.fmt_read, self.fmt_write)

    def _encode_read(self, subsys, param):
        cmd = self._fmt_cmd_read(subsys, param)
        self.socket.write(cmd)
        ans = self.socket.readline()
        return ans.strip()

    def _encode_write(self, subsys, param, val):
        cmd = self._fmt_cmd_write(subsys, param, val)
        self.socket.write(cmd)

    def _fmt_cmd_read(self, subsys, param):
        """ Return string ready to be sent to the hardware. """
        return self.fmt_read.format(subsys=subsys.__dict__,
                                    protocol=self.__dict__,
                                    param=param.__dict__)

    def _fmt_cmd_write(self, subsys, param, val):
        """ Return string ready to be sent to the hardware. """
        return self.fmt_write.format(subsys=subsys.__dict__,
                                     protocol=self.__dict__,
                                     param=param.__dict__,
                                     val=val)


class Subsystem(object):

    """
    A logical group of one or more commands (`Parameters` and
    `Actions`).

    The commands can be accessed directly on the Subsystem.  Further,
    another interface providing accessors to the commands and their
    attributes is generated on the fly.

    This accessor-based interface follows simple rules:
        - an `Action` is executed by prefixing its name with ``do_`` so
          that an Action ``a`` can be accessed with :meth:`do_a`.
        - getter and setter functions have the name of the `Parameter`
          prefixed with ``get_`` and ``set_`` so that a Parameter ``p``
          can be accessed with :meth:`get_p` and :meth:`set_p`.
        - other `Parameter` attributes are accessed by suffixing the
          Parameter's name with ``_is_readonly``, ``_minimum``,
          ``_maximum``, and ``_signal``.

    Printing a Subsystem returns a summary of its interface.

    Parameters
    ----------
    protocol : Protocol
        Protocol used by this subsystem to communicate with the
        hardware.

    """
    def __init__(self, protocol):
        self.protocol = protocol
        self._signals = dict()

    def __repr__(self):
        return "%s(protocol=%r)" % (self.__class__.__name__, self.protocol)

    def __str__(self):
        contents = [
            (name, type(obj).__name__, obj.__doc__)
            for name, obj in vars(type(self)).iteritems()
            if isinstance(obj, Parameter) or isinstance(obj, Action)]
        fieldlength = [max(len(str(field)) for field in line)
                       for line in zip(*contents)]
        return os.linesep.join(
            ["%s <0x%x>" % (self.__class__.__name__, id(self))] +
            ["%-{0}s %-{1}s %s".format(*fieldlength)
             % (name, typ, doc) for name, typ, doc in sorted(contents)])

    def __getattr__(self, attr_name):

        def getter(instance):
            return command.__get__(instance)

        def setter(instance, value):
            command.__set__(instance, value)

        def signal(instance):
            return instance._signals.setdefault(command, SignalProxy())

        def is_readonly(instance):
            return command.read_only

        def minimum(instance):
            return command.minimum

        def maximum(instance):
            return command.maximum

        def __get_property(prop_name):
            try:
                return vars(type(self))[prop_name]
            except KeyError:
                raise AttributeError

        prefixed = dict(get_=getter, set_=setter, do_=getter)
        try:
            prefix, function = ((p, f) for (p, f) in prefixed.iteritems()
                                if attr_name.startswith(p)).next()
        except StopIteration:
            pass
        else:
            prop_name = attr_name[len(prefix):]
            try:
                command = __get_property(prop_name)
                if (isinstance(command, Action) and prefix not in ("do_",)):
                    # Action only has `do_`
                    raise AttributeError
                elif (isinstance(command, Parameter) and prefix in ("do_",)):
                    raise AttributeError
            except AttributeError:
                return object.__getattribute__(self, attr_name)
            else:
                return self.__dict__.setdefault(
                    attr_name, types.MethodType(function, self, type(self)))

        suffixed = dict(_is_readonly=is_readonly,
                        _minimum=minimum,
                        _maximum=maximum,
                        _signal=signal)
        try:
            suffix, function = ((s, f) for (s, f) in suffixed.iteritems()
                                if attr_name.endswith(s)).next()
        except StopIteration:
            pass
        else:
            prop_name = attr_name[:-len(suffix)]
            try:
                command = __get_property(prop_name)
                if (isinstance(command, Action)):
                    # no Action with suffix
                    raise AttributeError
            except AttributeError:
                return object.__getattribute__(self, attr_name)
            else:
                return self.__dict__.setdefault(
                    attr_name, types.MethodType(function, self, type(self)))

        return object.__getattribute__(self, attr_name)

    @classmethod
    def add_parameter_by_name(cls, attr_name, *args, **kwargs):
        """ Helper to batch set parameters.

        Parameters
        ----------
        attr_name : str
            Name the new `Parameter`.
        args, kwargs : optional
            Passed to :meth:`Parameter.__init__`.
        """
        setattr(cls, attr_name, Parameter(*args, **kwargs))

    @classmethod
    def add_action_by_name(cls, attr_name, *args, **kwargs):
        """ Helper to batch set actions.

        Parameters
        ----------
        attr_name : str
            Name the new `Action`.
        args, kwargs : optional
            Passed to :meth:`Action.__init__`
        """
        setattr(cls, attr_name, Action(*args, **kwargs))


class Instrument(object):

    """
    Class containing the subsystems.

    If a `Subsystem` is named ``main`` in the class, it can be accessed
    directly on the `Instrument`.  That is
    ``instrument_obj.main.parameter_name`` is essentially the same as
    ``instrument_obj.parameter_name``.  This is particularly useful in
    instruments that contain a single Subsystem and in an interactive
    session.

    This is the class that is directly exposed to the user.

    Printing an Instrument returns a summary of its interface.

    """
    def __init__(self, socket=None, async=False):
        self.__socket = socket
        self.__async = async

    def __repr__(self):
        return "%s(socket=%r, async=%r)" % (
            self.__class__.__name__,
            self.__socket,
            self.__async)

    def __str__(self):
        name = "Instrument %s" % self.__class__.__name__
        buf = [name, len(name) * "="]
        for name, obj in ((name, obj)
                          for name, obj in vars(self).iteritems()
                          if isinstance(obj, Subsystem)):
            header = "%s subsystem" % name
            buf.extend([header, len(header) * "-", "%s" % obj])
        return os.linesep.join(buf)

    def __getattr__(self, attr_name):
        try:
            return object.__getattribute__(self, attr_name)
        except AttributeError:
            # attr not in self, try in self.main
            try:
                main = self.__dict__["main"]
                return main.__getattr__(attr_name)
            except (KeyError, AttributeError):
                # correct error message
                return object.__getattribute__(self, attr_name)

    def __setattr__(self, attr_name, value):
        try:
            main = self.__dict__["main"]
            if hasattr(main, attr_name):
                main.__setattr__(attr_name, value)
            else:
                raise AttributeError
        except (KeyError, AttributeError):
            object.__setattr__(self, attr_name, value)


class Adapter(object):

    """
    This class implements the adapter pattern in python.

    The adapter pattern is a design pattern that translates one
    interface for a class into a compatible interface. (wikipedia)

    Parameters
    ----------
    adaptee : object
        Object to adapt.
    mapping : dict
        Mapping in the form {adaptor_attr : adaptee_attr}

    """
    def __init__(self, adaptee, mapping):
        self.adaptee = adaptee
        self.mapping = mapping

    def __repr__(self):
        return "%s(adaptee=%r, mapping=%r)" % \
                (self.__class__.__name__, self.adaptee, self.mapping)

    def __getattr__(self, attr_name):
        """ Recursion until match found in self.mapping. """
        try:
            return reduce(getattr,
                          self.mapping[attr_name].split("."), self.adaptee)
        except KeyError:
            return super(Adapter, self).__getattribute__(attr_name)


class DriverAdapter(QObject, Adapter):  # inherits QObject for moveToThread

    """
    Add access to the ``get_``, ``set_``, ``do_``, ``_signal``,
    ``_is_readonly``, ``_minimum``, and ``_maximum`` functions to the
    mapping.

    See also
    --------
    Adapter : Class that this class inherits.
    Subsystem : Class that generates the ``get_``, etc. functions.

    """
    prefixes = "get_ set_ do_".split()
    suffixes = "_signal _is_readonly _minimum _maximum".split()

    def __init__(self, adaptee, mapping):
        def _prefix(pre, path):
            path = path.split(".")
            path[-1] = "%s%s" % (pre, path[-1])
            return ".".join(path)

        def _suffix(path, suf):
            path = path.split(".")
            path[-1] = "%s%s" % (path[-1], suf)
            return ".".join(path)

        prefixed = {_prefix(pre, key): _prefix(pre, value)
                    for (key, value) in mapping.iteritems()
                    for pre in DriverAdapter.prefixes}
        suffixed = {_suffix(key, suf): _suffix(value, suf)
                    for (key, value) in mapping.iteritems()
                    for suf in DriverAdapter.suffixes}
        # deep copy mapping
        _mapping = {k: v for k, v in mapping.iteritems()}
        _mapping.update(prefixed)
        _mapping.update(suffixed)

        QObject.__init__(self)
        Adapter.__init__(self, adaptee, _mapping)

    def __repr__(self):
        return Adapter.__repr__(self)

    def __str__(self):
        return Adapter.__str__(self)

    def __getattr__(self, attr_name):
        return Adapter.__getattr__(self, attr_name)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
