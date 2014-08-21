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
    from lindaq import DioProtocol, AioProtocol
else:
    from windaq import DioProtocol
    from windaq import VoltageAioProtocol as AioProtocol

import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


# NI 622x range | precision
# -10.0 to +10.0 V -> 320 muV
#  -5.0 to  +5.0 V -> 160 muV
#  -1.0 to  +1.0 V ->  32 muV
#  -0.2 to  +0.2 V -> 6.4 muV


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

    The NI 622x cards have the following nodes:
        - 32 AI channels: ai[0-31]
        - 4 AO channels: ao[0-3]
        - 32 DIO channels on port0: port0/line[0-31]
        - 8 DIO channels on port1: port1/line[0-7]
        - 8 DIO channels on port2: port2/line[0-7]

    Args:
        device: The name of the device.

    """
    def __init__(self, device, parent=None):
        super(Daq, self).__init__(parent)
        self.digitalIO = Subsystem(device, self)
        self.digitalIO.setProtocol(DioProtocol(self))
        self.digitalIO.state = Cmd(None, rfunc=bool, access=Access.RW)
        self.voltage = Subsystem(device, self)
        self.voltage.setProtocol(AioProtocol(self))
        self.voltage.ai = Cmd(None, minimum=-10, maximum=10, access=Access.RO)
        self.voltage.ao = Cmd(None, minimum=-10, maximum=10, access=Access.WO)

