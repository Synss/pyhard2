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
from time import sleep
import sys

if sys.platform == "linux2":
    from lindaq import DioProtocol, AioProtocol
else:
    from windaq import DioProtocol, AioProtocol

import pyhard2.driver as drv
Access = drv.Access


# NI 622x range | precision
# -10.0 to +10.0 V -> 320 muV
#  -5.0 to  +5.0 V -> 160 muV
#  -1.0 to  +1.0 V ->  32 muV
#  -0.2 to  +0.2 V -> 6.4 muV


class DioCommand(drv.Command):

    """Command for digital in-out lines."""

    def __init__(self, read_line, write_line=None, access=Access.RW):
        super(DioCommand, self).__init__(read_line, write_line, access)

    def switch(self):
        """Change the state."""
        self.write(not self.read())

    def pulse(self, time_on, time_off=0.0):
        """Create a pulse."""
        for delay in (time_on, time_off):
            self.switch()
            sleep(delay)


class AiCommand(drv.Command):

    """Command for analog in lines."""

    def __init__(self, phys_channel, minimum=-10, maximum=10):
        super(AiCommand, self).__init__(phys_channel, None,
                                        minimum=minimum, maximum=maximum,
                                        access=Access.RO)


class AoCommand(drv.Command):

    """Command for analog out lines."""

    def __init__(self, phys_channel, minimum=-10, maximum=10):
        super(AoCommand, self).__init__(None, phys_channel,
                                        minimum=minimum, maximum=maximum,
                                        access=Access.WO)


class Ni622x(drv.Subsystem):

    """Driver for the NI 622x cards."""

    def __init__(self, address):
        ## Digital channels
        self.digitalIO = drv.Subsystem(self)
        self.digitalIO.setProtocol(DioProtocol(self))
        # port 0, 16 DIO channels
        for channel in range(32):
            phys_channel = "%s/port0/line%i" % (address, channel)
            self.digitalIO.__setattr__(phys_channel, DioCommand(phys_channel))
        # port 1, 8 DIO channels
        for channel in range(8):
            phys_channel = "%s/port0/line%i" % (address, channel)
            self.digitalIO.__setattr__(phys_channel, DioCommand(phys_channel))
        # port 2, 8 DIO channels
        for channel in range(8):
            phys_channel = "%s/port0/line%i" % (address, channel)
            self.digitalIO.__setattr__(phys_channel, DioCommand(phys_channel))
        ## Analog channels
        self.analogIO = drv.Subsystem(self)
        self.analogIO.setProtocol(AioProtocol(self))
        # 4 AO channels
        for channel in range(4):
            phys_channel = "%s/ao%i" % (address, channel)
            self.analogIO.__setattr__(phys_channel, AoCommand(phys_channel))
        # 4 AI channels
        for channel in range(4):
            phys_channel = "%s/ai%i" % (address, channel)
            self.analogIO.__setattr__(phys_channel, AiCommand(phys_channel))

