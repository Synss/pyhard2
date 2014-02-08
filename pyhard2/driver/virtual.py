"""
Virtual instrument drivers
==========================

Virtual instrument driver used to test GUIs.

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
Parameter = drv.Parameter
Action = drv.Action
import pyhard2.pid as pid


warnings.simplefilter("once")


class PidSubsystem(drv.Subsystem):

    """
    Wrap `pyhard2.pid.PidController`.

    See also
    --------
    pyhard2.pid.PidController : The PID controller.
    pyhard2.driver.WrapperProtocol : The wrapper.
    
    """
    output = drv.SignalProxy()

    def __init__(self):
        self.__pid = pid.PidController()
        protocol = drv.WrapperProtocol(self.__pid, async=True)
        super(PidSubsystem, self).__init__(protocol)
        for name in """ proportional
                        integral_time
                        derivative_time
                        vmin
                        vmax
                        setpoint
                        anti_windup
                        proportional_on_pv
                    """.split():
            self.add_parameter_by_name(name, name)
        self.add_action_by_name("reset", "reset")

    #@Slot(float)
    def compute_output(self, measure):
        """ Return the output from the PID, provided `measure`. """
        pidout = self.__pid.compute_output(measure)
        self.output.emit(pidout)


class VirtualInputSubsystem(drv.Subsystem):

    """
    Virtual subsystem that returns a measure as a function of the
    output of the system.

    """
    def __init__(self):
        super(VirtualInputSubsystem, self).__init__(
            drv.ProtocolLess(None, async=False))
        self._sysout = 0.0

    #@Slot(float)
    def set_sysout(self, sysout):
        """ Set the output of the system. """
        self._sysout = sysout

    def __get_measure(self):
        return self._sysout / 2.0

    measure = Parameter(__get_measure, read_only=True)


class VirtualOutputSubsystem(drv.Subsystem):

    """
    Virtual subsystem that computes a response from the system using the
    state-space representation given in `system`.

    """
    def __init__(self, system):
        super(VirtualOutputSubsystem, self).__init__(
            drv.ProtocolLess(None, async=False))
        self._system = (sig.tf2ss([10.0], [20.0, 2.0])
                        if system is None else system)
        self._inputs = [0.0, 0.0]  # U
        self._times = [0.0, 0.01]  # T
        self._noise = 1.0          # %
        self._start = time.time()

    #@Slot(float)
    def append_input(self, input):
        """ Sets current `input`. """
        self._times.append(time.time() - self._start)
        self._inputs.append(input)

    def __get_output(self):
        times, yout, xout = sig.lsim(self._system, self._inputs, self._times)
        return yout[-1] + random.gauss(yout[-1], self._noise)

    output = Parameter(__get_output, read_only=True)

    def __get_noise(self):
        return self._noise

    def __set_noise(self, value):
        self._noise = value

    noise = Parameter(__get_noise, __set_noise)


class VirtualInstrument(drv.Instrument):

    """
    Virtual instrument that links the `VirtualInputSubsystem` and
    the `VirtualOutputSubsystem` via the `PidSubsystem`.

    Attributes
    ----------
    pid : PidSubsystem
    input : VirtualInputSubsystem
    output : VirtualOutputSubsystem

    """
    def __init__(self, system=None, async=False):
        super(VirtualInstrument, self).__init__()
        self.pid = PidSubsystem()
        self.input = VirtualInputSubsystem()
        self.output = VirtualOutputSubsystem(system)

        self.input.measure_signal().connect(self.pid.compute_output)
        self.pid.output_signal().connect(self.output.append_input)
        self.output.output_signal().connect(self.input.set_sysout)


virtual_mapper = dict(
    setpoint="pid.setpoint",
    pid_gain="pid.proportional",
    pid_integral="pid.integral_time",
    pid_derivative="pid.derivative_time",
    output="output.output",
    measure="input.measure")


def main(argv):
    import matplotlib.pyplot as plt

    vi = VirtualInstrument()
    #vi.input.noise = 0.0

    vi.pid.gain = 4.0
    vi.pid.integral = 1.0
    vi.pid.setpoint = 0.0
    vi.output.noise = 0.0
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
            vi.pid.setpoint += 10.0
            step_done = True
        time_.append((time.time() - start) / time_factor)
        measure.append(vi.input.measure)
        output.append(vi.output.output)
        setpoint.append(vi.pid.setpoint)
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
