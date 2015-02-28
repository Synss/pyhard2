"""Virtual instrument driver used to test GUIs.

"""
import sys
import time
import random
import warnings
try:
    import scipy.signal as sig
except ImportError:
    sys.stderr.write("Virtual instrument not available.\n")
    sys.stderr.flush()
    raise

import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access
import pyhard2.pid as pid


warnings.simplefilter("once")


class Pid(pid.PidController):

    """Wrap `pyhard2.pid.PidController` to handle asynchronous setting
    of `output` and `measure`.

    """
    def __init__(self,
                 proportional=2.0, integral_time=0.0, derivative_time=0.0,
                 vmin=0.0, vmax=100.0):
        super(Pid, self).__init__(proportional, integral_time, derivative_time,
                                  vmin, vmax)
        self.measure = 0.0

    @property
    def output(self):
        return self.compute_output(self.measure)


class Input(object):

    """Linear input simulator."""

    def __init__(self):
        self.sysout = 0.0

    @property
    def measure(self):
        return self.sysout / 2.0


class Output(object):

    """Output simulator using a transfer function."""

    def __init__(self):
        self.system = sig.tf2ss([10.0], [20.0, 2.0])
        self.noise = 1.0          # %
        self.inputs = [0.0, 0.0]  # U
        self.times = [0.0, 0.01]  # T
        self.start = time.time()

    @property
    def input(self):
        return self.inputs[-1]

    @input.setter
    def input(self, value):
        self.times.append(time.time() - self.start)
        self.inputs.append(value)

    @property
    def output(self):
        times, yout, xout = sig.lsim(self.system, self.inputs, self.times)
        output = yout[-1] + random.gauss(yout[-1], self.noise)
        return output.item()  # conversion from numpy.float64


class PidSubsystem(drv.Subsystem):

    """The subsystem for the PID."""

    def __init__(self, parent,
                 proportional=2.0, integral_time=0.0, derivative_time=0.0,
                 vmin=0.0, vmax=100.0, spmin=0.0, spmax=100.0):
        super(PidSubsystem, self).__init__(parent)
        self.setProtocol(drv.ObjectWrapperProtocol(Pid(
            proportional, integral_time, derivative_time, vmin, vmax)))
        self.measure = Cmd("measure", access=Access.WO)
        self.output = Cmd("output", access=Access.RO)
        self.setpoint = Cmd("setpoint", minimum=spmin, maximum=spmax)
        self.proportional = Cmd("proportional")
        self.integral_time = Cmd("integral_time")
        self.derivative_time = Cmd("derivative_time")
        self.vmin = Cmd("vmin")
        self.vmax = Cmd("vmax")
        self.anti_windup = Cmd("anti_windup")


class VirtualInstrument(drv.Subsystem):

    """Driver for virtual instruments with a PID.

    .. graphviz:: gv/VirtualInstrument.txt

    """
    def __init__(self, socket=None):
        super(VirtualInstrument, self).__init__()
        self.pid = PidSubsystem(self)
        # Input subsystem
        self.input = drv.Subsystem(self)
        self.input.setProtocol(drv.ObjectWrapperProtocol(Input()))
        self.input.sysout = Cmd("sysout")
        self.input.measure = Cmd("measure", access=Access.RO)
        # Output subsystem
        self.output = drv.Subsystem(self)
        self.output.setProtocol(drv.ObjectWrapperProtocol(Output()))
        self.output.input = Cmd("input")
        self.output.output = Cmd("output", access=Access.RO)
        self.output.noise = Cmd("noise")
        # Connections
        self.input.measure.signal.connect(self.pid.measure.write)
        self.input.measure.signal.connect(
            lambda value, node: self.pid.output.read(node))
        self.pid.output.signal.connect(self.output.input.write)
        self.output.output.signal.connect(self.input.sysout.write)


def main(argv):
    import matplotlib.pyplot as plt

    vi = VirtualInstrument()
    #vi.input.noise = 0.0

    vi.pid.proportional.write(1.0)
    vi.pid.integral_time.write(4.0)
    vi.pid.derivative_time.write(0.8)
    vi.pid.setpoint.write(0.0)
    vi.output.noise.write(0.0)
    step_done = False

    measure = []
    time_ = []
    output = []
    setpoint = []

    start = time.time()
    time_factor = 1.0
    print("Please wait\t")
    while time.time() - start < 10.0 * time_factor:
        if (not step_done and time.time() - start > 1.5 * time_factor):
            vi.pid.setpoint.write(vi.pid.setpoint.read() + 10.0)
            step_done = True
        time_.append((time.time() - start) / time_factor)
        measure.append(vi.input.measure.read())
        output.append(vi.output.output.read())
        setpoint.append(vi.pid.setpoint.read())
        print ("MEAS: %s  OUT: %s  SP: %s" % (
            measure[-1], output[-1], setpoint[-1]))
        time.sleep(0.5 * time_factor)

    plt.plot(time_, measure, label="measure")
    plt.plot(time_, output, label="output")
    plt.plot(time_, setpoint, label="setpoint")
    plt.xlabel("time / s")
    plt.ylabel("intensity")
    plt.legend()
    plt.show()


if __name__ == "__main__":
    main(sys.argv)
