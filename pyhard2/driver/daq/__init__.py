"""Drivers for National Instrument hardware.

The materials supported is the one supported by NI-DAQmx on Windows and
comedi on Linux.

Note:
    - The driver depends on `pycomedi <https://pypi.python.org/pypi/pycomedi/>`_
      on Linux or `PyLibNIDAQmx <http://code.google.com/p/pylibnidaqmx/>`_
      on Windows.
    - The driver requires `numpy` on all platform.

Reference:
   - `NI-DAQmx Software <http://www.ni.com/dataacquisition/d/nidaqmx.htm>`_
   - `comedi <http://www.comedi.org/>`_

"""
import sys

if sys.platform == "linux2":
    from .lindaq import DioProtocol, AioProtocol
else:
    from .windaq import DioProtocol
    from .windaq import VoltageAioProtocol as AioProtocol

import pyhard2.driver as drv
Access = drv.Access


# NI 622x range | precision
# -10.0 to +10.0 V -> 320 muV
#  -5.0 to  +5.0 V -> 160 muV
#  -1.0 to  +1.0 V ->  32 muV
#  -0.2 to  +0.2 V -> 6.4 muV


class Cmd(drv.Command):

    """`Command` without `reader`."""

    class Context(drv.Context):

        """`Context` with `minimum` and `maximum` attributes."""

        def __init__(self, command, value=None, node=None):
            super(Cmd.Context, self).__init__(command, value, node)
            self.minimum = command.minimum
            self.maximum = command.maximum

    def __init__(self, **kwargs):
        super(Cmd, self).__init__(reader=None, **kwargs)


class Subsystem(drv.Subsystem):

    """A subsytem with a `device` attribute.

    Args:
        device (string): The device name.

    """
    def __init__(self, device, parent=None):
        super(Subsystem, self).__init__(parent)
        self.device = device


class Daq(drv.Subsystem):

    """Driver for DAQ hardware.

    On windows, the node names are ``portN/lineM`` for the digital
    in/out channels and ``aiN`` or ``aoN`` for the analog input and
    output.

    On linux, the node names are ``SUBDEVICE.CHANNEL``, that is the
    number of the `subdevice` and of the `channel` separated with a dot
    ``.``.

    Args:
        device (str): The name of the device on windows or its address
            (example ``/dev/comedi0``) on linux.

    .. graphviz:: gv/Daq.txt

    Example:
        NI 622x cards have following nodes:

        - 32 AI channels: ai[0-31]
        - 4 AO channels: ao[0-3]
        - 32 DIO channels on port0: port0/line[0-31]
        - 8 DIO channels on port1: port1/line[0-7]
        - 8 DIO channels on port2: port2/line[0-7]

        Use as follows

        >>> driver = Daq("NAME")  # The actual device name
        >>> driver.state.read("port0/line3")  # windows names
        ... False
        >>> driver.state.write(True, "port0/line3")
        >>> driver.state.read("port0/line3")
        ... True
        >>> driver.voltage.ai.read("ai0")
        ... 0.5
        >>> driver.voltage.ao.write(1.0, "ao0")

    """
    def __init__(self, device, parent=None):
        super(Daq, self).__init__(parent)
        self.digitalIO = Subsystem(device, self)
        self.digitalIO.setProtocol(DioProtocol(self))
        self.digitalIO.state = Cmd(rfunc=bool, access=Access.RW)
        self.voltage = Subsystem(device, self)
        self.voltage.setProtocol(AioProtocol(self))
        self.voltage.ai = Cmd(minimum=-10, maximum=10, access=Access.RO)
        self.voltage.ao = Cmd(minimum=-10, maximum=10, access=Access.WO)

