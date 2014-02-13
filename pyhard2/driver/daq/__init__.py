"""
NI-DAQ drivers
==============

Drivers for National Instrument hardware.  The materials supported is
the one supported by NI-DAQmx on Windows and comedi on Linux.


Notes
-----
- The driver depends on `pycomedi
  <https://pypi.python.org/pypi/pycomedi/>`_ on Linux or `PyLibNIDAQmx
  <http://code.google.com/p/pylibnidaqmx/>`_ on Windows.
- The driver requires `numpy` on all platform.


References
----------
- `NI-DAQmx Software <http://www.ni.com/dataacquisition/d/nidaqmx.htm>`_
- `comedi <http://www.comedi.org/>`_

"""

from time import sleep
import sys
import numpy as np

if sys.platform == "linux2":
    from lindaq import *
else:
    from windaq import *

import pyhard2.driver as drv
Parameter = drv.Parameter
Action = drv.Action


# NI 622x range | precision
# -10.0 to +10.0 V -> 320 muV
#  -5.0 to  +5.0 V -> 160 muV
#  -1.0 to  +1.0 V ->  32 muV
#  -0.2 to  +0.2 V -> 6.4 muV


class DioSubsystem(drv.Subsystem):
    """Subsystem for digital input/output."""

    def __get_state(self):
        return bool(self.protocol.socket.read())

    def __set_state(self, state):
        self.protocol.socket.write(bool(state))

    state = Parameter(__get_state, __set_state)

    def __do_switch(self):
        self.state = not self.state

    switch = Action(__do_switch)

    def __do_pulse(self, time_on, time_off=0.0):
        for delay in (time_on, time_off):
            self.switch()
            sleep(delay)

    pulse = Action(__do_pulse)


class DioInstrument(drv.Instrument):
    """Instrument for digital input/output."""

    def __init__(self, socket, async=False):
        super(DioInstrument, self).__init__()
        self.main = DioSubsystem(drv.ProtocolLess(socket, async))


class AiSubsystem(drv.Subsystem):
    """Subsystem for analog input."""

    samples = 100

    def __get_measure(self):
        return float(np.average(self.protocol.socket.read(self.samples)))

    measure = Parameter(__get_measure, read_only=True)


class AiInstrument(drv.Instrument):
    """Instrument for analog input."""

    def __init__(self, socket, async=False):
        super(AiInstrument, self).__init__()
        self.main = AiSubsystem(drv.ProtocolLess(socket, async))


class AoSubsystem(drv.Subsystem):
    """Subsystem for analog output."""

    def __set_measure(self, data):
        self.protocol.socket.write(data)

    measure = Parameter(None, __set_measure)


class AoInstrument(drv.Instrument):
    """Instrument for analog output."""

    def __init__(self, socket, async=False):
        super(AoInstrument, self).__init__()
        self.main = AoSubsystem(drv.ProtocolLess(socket, async))
