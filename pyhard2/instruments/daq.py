from time import sleep
import numpy as np

# http://code.google.com/p/pylibnidaqmx
from nidaqmx import DigitalOutputTask, DigitalInputTask
from nidaqmx import AnalogInputTask, AnalogOutputTask


from driver import *


__all__ = ["Valve", "Temperature", "Pressure"]

# NI 622x range | precision
# -10.0 to +10.0 V -> 320 muV
#  -5.0 to  +5.0 V -> 160 muV
#  -1.0 to  +1.0 V ->  32 muV
#  -0.2 to  +0.2 V -> 6.4 muV


class DioTask(DigitalOutputTask, DigitalInputTask):
    # Scpi: Signal switcher

    channel_type = "DO"

    def create_channel(self, *args, **kwargs):
        DigitalOutputTask.create_channel(self, *args, **kwargs)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - Tasks/Sockets

class AiSocket(AnalogInputTask):

    def __init__(self, name=None, *args, **kwargs):
        super(AiSocket, self).__init__(name)
        self.create_voltage_channel(*args, **kwargs)

    def read(self, n=100):
        self.socket.start()
        data = np.average(AnalogInputTask.read(n))
        self.socket.stop()
        return data

    def write(self, x):
        raise NotImplementedError


class AoSocket(AnalogOutputTask):

    def __init__(self, name=None, *args, **kwargs):
        super(AoSocket, self).__init__(name)
        self.create_voltage_channel(*args, **kwargs)

    def read(self):
        raise NotImplementedError

    def write(self, x):
        AnalogOutputTask.write(x)


class DioSocket(DioTask):

    def __init__(self, name=None, *args, **kwargs):
        super(DioSocket, self).__init__(name)
        self.create_channel(*args, **kwargs)

    def read(self):
        return DioSocket.read(self, 1)[0].item()

    def write(self, state):
        # for compatibility with numpy
        if hasattr(state, "tolist"): state = state.tolist()[0]
        DioSocket.write(self, state)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - Protocols

class DaqProtocol(AbstractProtocol):

    def __init__(self, socket):
        # socket == task
        self._callback = {}
        super(DaqProtocol, self).__init__(socket)

    def _encode_read(self, subsys, param):
        return self._callback[param.getcmd]()

    def _encode_write(self, subsys, param, val):
        self._callback[param.getcmd](val)


class DioProtocol(DaqProtocol):

    HIGH, LOW = True, False

    def __init__(self, socket):
        super(DioProtocol, self).__init__(socket)
        self._callback.update(GET_STATE=self.get_state,
                              SET_STATE=self.set_state,
                              SWITCH=self.switch)

    def get_state(self):
        return self.socket.read() == DioProtocol.HIGH

    def set_state(self, val):
        self.socket.write(val)

    state = property(get_state, set_state)

    def switch(self):
        self._state = not self._state


class AiProtocol(DaqProtocol):

    def __init__(self, socket):
        super(AiProtocol, self).__init__(socket)
        self._callback.update(GET_MEASURE=self.get_measure)

    def get_measure(self, n=100):
        self.socket.start()
        data = np.average(self.socket.read(n))
        self.socket.stop()
        return data

    measure = property(get_measure)


class ValveProtocol(DioProtocol):

    OPEN, CLOSED = DioProtocol.HIGH, DioProtocol.LOW

    def __init__(self, socket):
        super(ValveProtocol, self).__init__(socket)
        self._callback.update(OPEN=self.open,
                              CLOSE=self.close)

    def close(self):
        self._state = ValveProtocol.CLOSED

    def open(self):
        self._state = ValveProtocol.OPEN


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - Subsystems

class DioSubsystem(Subsystem):

    def __init__(self, protocol):
        super(DioSubsystem, self).__init__(protocol)

    state = Parameter("SET_STATE", "GET_STATE")
    switch = Action("SWITCH")


class AiSubsystem(Subsystem):

    def __init__(self, protocol):
        super(AiSubsystem, self).__init__(protocol)

    measure = Parameter("GET_MEASURE", read_only=True)


class AoSubsystem(Subsystem):

    def __init__(self, protocol):
        super(AoSubsystem, self).__init__(protocol)
        raise NotImplementedError

    measure = Parameter("SET_MEASURE")


class ValveSubsystem(DioSubsystem):

    def __init__(self, protocol):
        super(ValveSubsystem, self).__init__(protocol)

    open = Action("OPEN")
    close = Action("CLOSE")


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - Instruments

class Valve(Instrument):

    OPEN = ValveProtocol.OPEN
    CLOSE = ValveProtocol.CLOSE

    def __init__(self, task=None):
        protocol = ValveProtocol(task)
        super(Valve, self).__init__(protocol)
        self.main = ValveSubsystem(protocol)


class Temperature(Instrument):

    def __init__(self, task=None):
        protocol = AiProtocol(task)
        super(Temperature, self).__init__(protocol)
        self.main = AiSubsystem(protocol)

    celsius = Parameter("GET_MEASURE", getCB=lambda x: 100.0 * x)
    kelvin = Parameter("GET_MEASURE", getCB=lambda x: 273.15 + 100.0 * x)
    fahrenheit = Parameter("GET_MEASURE",
                           getCB=lambda x: 1.8 * 100.0 * x + 32.0)


class Pressure(Instrument):

    def __init__(self, task=None):
        protocol = AiProtocol(task)
        super(Pressure, self).__init__(protocol)
        self.main = AiSubsystem(protocol)

    mbar = Parameter("GET_MEASURE", getCB=lambda x: 100.0 * x)


# - - - - - - - - - - - - - - - - - - - - - - - - - - utility functions

def pulse(dio, time_on, time_off=0.0):
    for delay in (time_on, time_off):
        dio.switch()
        sleep(delay)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - test functions

def test_valve():
    valve = Valve(DioSocket("Circat1/port0/line0", "DIOTest"))
    pulse(valve, 1.0)

def test_temperature():
    socket = AiSocket(name="T1",
                      channel="Circat1/ai1",
                      terminal="rse",
                      min_val=-1.0,
                      max_val=1.0)
    socket.configure_timing_sample_clock(rate=2000.0)
    t = Temperature(socket)
    print t.protocol.socket.read(200)

def test_pressure():
    socket = AiSocket(name="P1",
                      channel="Circat1/ai16",
                      terminal="rse",
                      min_val=-10.0,
                      max_val=10.0)
    socket.configure_timing_sample_clock(rate=1000.0)
    p = Pressure(socket)
    print p.protocol.socket.read(100)
