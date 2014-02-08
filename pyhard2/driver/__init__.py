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
    """A simple identity function."""
    return args[0] if len(args) is 1 else args


class Serial(serial.Serial):

    """Fix `readline` in `pyserial`."""

    def __init__(self, port=None, newline="\n", *args, **kwargs):
        super(Serial, self).__init__(port, *args, **kwargs)
        self.newline = newline

    def readline(self):
        """Implement own readline since changing EOL character with `io`
        does not work well."""
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
    getter_func : function
        Apply to the value returned by the hardware.
    doc : docstring

    Notes
    -----
    Implements `__call__`.

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
        Command to set the parameter.
    minimum, maximum : number, optional
        Minimum and maximum value used for data validation.  Values
        passed to the parameter exceeding `minimum` or `maximum` are silently
        coerced to avoid hardware errors
    read_only : bool
        An AttributeError is raised if an attempt to write to a `read
        only` parameter is done.
    getter_func, setter_func : function
    doc : docstring

    Notes
    -----

    Implements `__get__` and `__set__`.

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
        """
        self._set(subsys, val)


class AbstractProtocol(object):

    """
    An abstract class to implement protocols.

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

    """ Look up `param.getcmd` or `param.setcmd` in `wrapped_obj`'s
        attributes. """

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
    Protocol to use with hardware that does not need framing.

    Notes
    -----
    Requires that `setcmd` and `getcmd` from the `Subsystem` are
    callbacks.  The :mod:`pyhard2.driver.virtual` driver provides an
    example usage.

    """

    def __init__(self, socket, async):
        super(ProtocolLess, self).__init__(socket, async)

    def _encode_read(self, subsys, param):
        return param.getcmd(subsys)

    def _encode_write(self, subsys, param, val):
        param.setcmd(subsys, val)


class SerialProtocol(AbstractProtocol):

    """
    Implement a protocol for use for serial communication.

    Parameters
    ----------
    fmt_read : str
        string with placeholders to format read command
    fmt_write : str
        string with placeholders to format write command

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
        """Return string ready to be sent to the hardware."""
        return self.fmt_read.format(subsys=subsys.__dict__,
                                    protocol=self.__dict__,
                                    param=param.__dict__)

    def _fmt_cmd_write(self, subsys, param, val):
        """Return string ready to be sent to the hardware."""
        return self.fmt_write.format(subsys=subsys.__dict__,
                                     protocol=self.__dict__,
                                     param=param.__dict__,
                                     val=val)


class Subsystem(object):

    """
    A logical group of one or more `Parameter`.
    
    Parameters
    ----------
    protocol : Protocol
        Protocol used by this subsystem to communicate with the hardware.

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
                return types.MethodType(function, self, type(self))

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
                return types.MethodType(function, self, type(self))

        return object.__getattribute__(self, attr_name)

    @classmethod
    def add_parameter_by_name(cls, attr_name, *args, **kwargs):
        """Helper to batch set parameters.

        Parameters
        ----------
        attr_name : str
            Name the new `Parameter`.
        args, kwargs : optional
            Passed to `Parameter.__init__()`.
        """
        setattr(cls, attr_name, Parameter(*args, **kwargs))

    @classmethod
    def add_action_by_name(cls, attr_name, *args, **kwargs):
        """Helper to batch set actions.

        Parameters
        ----------
        attr_name : str
            Name the new `Action`.
        args, kwargs : optional
            Passed to `Action.__init__()`
        """
        setattr(cls, attr_name, Action(*args, **kwargs))


class Instrument(object):

    """ Class containing the subsystems.
    
    This is the class that should be directly exposed to the user.

    Attributes
    ----------
    default : str
        Name the default `Subsystem`.

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
    Adapt `Instrument` interface by mapping attribute names.

    Parameters
    ----------
    adaptee : Instrument
        Instrument to adapt.
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

    """ Add get_, set_, do_ and _signal, _is_readonly, _minimum, and _maximum
        functions to the mapping. """

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

