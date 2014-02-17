"""
Watlow drivers
==============

Drivers for Watlow Series 988 family of controllers.


Communication using the XON/XOFF protocol follows:

.. uml::

    group Set
    User    ->  Instrument: = {mnemonic} {value}
    User    <-- Instrument: XOFF
    User    <-- Instrument: XON
    end

    group Query
    User    ->  Instrument: ? {mnemonic}
    User    <-- Instrument: XOFF
    User    <-- Instrument: XON{value}
    end


Notes
-----
The XON/XOFF protocol is implemented.

"""

from os import path

import pyhard2.driver as drv
import pyhard2.driver.input.odf as odf


class WatlowHardwareError(drv.HardwareError): pass


class WatlowDriverError(drv.DriverError): pass


class TestSocket(drv.TestSocketBase):

    def __init__(self, port=None, newline="\r"):
        super(TestSocket, self).__init__(
            {
                "? SP1\r": "\x13\x1125\r",
                "? PWR\r": "\x13\x115\r",
                "? ER2\r": "\x13\x110\r",
            },
            port, newline)

    def write(self, cmd):
        if cmd.startswith("="):
            equal, mnemo, val = cmd.split()
            self.msg["? %s\r" % mnemo] = "\x13\x11%s\r" % val
            self.cmd = "\x13\x11"
        else:
            drv.TestSocketBase.write(self, cmd)


class XonProtocol(drv.SerialProtocol):

    """Implement the XON/XOFF protocol."""

    _err = {0: "No error",
            1: "Transmit buffer overflow",
            2: "Receive buffer overflow",
            3: "Framing error",
            4: "Overrun error",
            5: "Parity error",
            6: "Talking out of turn",
            7: "Invalid reply error",
            8: "Noise error",
            20: "Command not found",
            21: "Prompt not found",
            22: "Incomplete command line",
            23: "Invalid character",
            24: "Number of chars. overflow",
            25: "Input out of limit",
            26: "Read only command",
            27: "Write only command",
            28: "Prompt not active"}

    def __init__(self, socket, async):
        super(XonProtocol, self).__init__(
            socket,
            async,
            fmt_read="? {param[getcmd]}\r",
            fmt_write="= {param[setcmd]} {val}\r",
        )

    def _xon(self):
        assert(self.socket.read(1) == "/x13")  # XOFF
        assert(self.socket.read(1) == "/x11")  # XON

    def _encode_read(self, subsys, param):
        cmd = self._fmt_cmd_read(subsys, param)
        self.socket.write(cmd)
        self._xon()
        ans = self.socket.readline()
        self._check_error(cmd)     # check for error
        return float(ans.strip())  # unicode to number

    def _encode_write(self, subsys, param, val):
        cmd = self._fmt_cmd_write(subsys, param, val)
        self.socket.write(cmd)
        self._xon()
        self._check_error(cmd)     # check for error

    def _check_error(self, cmd):
        self.socket.write("? ER2\r")
        self._xon()
        err_code = self.socket.readline()
        if not err_code.startswith("0"):
            try:
                err = XonProtocol._err[int(err_code)]
                raise drv.HardwareError(
                    "Command %r returned error: %s" %
                    (cmd, err))
            except KeyError:
                raise WatlowDriverError(
                    "Command %r returned unkwnown error: %s" %
                    (cmd, err_code))


class ModbusProtocol(drv.SerialProtocol):

    def __init__(self, socket):
        raise NotImplementedError

    def __repr__(self):
        return "%s(socket=%r)" % (self.__class__.__name__, self.socket)


def fahrenheit2celsius(x):
    """Conversion function."""
    return (float(x) - 32.0) / 1.8


class OperationPidASubsystem(drv.Subsystem):

    """Commands in the Operation -> PID A menu."""

    # Operation-PID A or B
    gain = drv.Parameter("PB1A", getter_func=float)
    # PB1B
    integral = drv.Parameter("IT1A", getter_func=float)
    # IT1B
    derivative = drv.Parameter("DE1A", getter_func=float)
    # DE1B
    # CT1A
    # CT1B


class OperationPidBSubsystem(drv.Subsystem):

    """Commands in the Operation -> PID B menu."""

    gain = drv.Parameter("PB2A", getter_func=float)
    # PB2B
    integral = drv.Parameter("IT2A", getter_func=float)
    # IT2B
    derivative = drv.Parameter("DE2A", getter_func=float)
    # DE2B
    # CT2A
    # CT2B
    # DBA
    # DBB


class Series988(drv.Instrument):

    """Instrument for the Watlow Series 988 family of controllers."""

    def __init__(self, socket, async=False):
        super(Series988, self).__init__()

        socket.timeout = 5.0
        socket.newline = "\r"

        protocol = XonProtocol(socket, async)

        # better approach to finding the filename in setuptools
        # using `pkg_resources` that also works in zipped egg
        filename = path.join(path.dirname(__file__), "watlow.fods")
        odf.instrument_from_workbook(filename, self, protocol, globals())

        self.operation_pid_A = OperationPidASubsystem(protocol)
        self.operation_pid_B = OperationPidBSubsystem(protocol)


def main(port=None):
    # port = "/dev/tty.PL2303-0000101D"
    if port:
        ser = drv.Serial(port)
    else:
        ser = drv.Serial()
    heater = Series988(ser)

    print(heater)

    print "Ambient temperature",
    print heater.factory_diagnostic.ambient_temperature
    print "Current SP",
    print heater.setpoint
    sp = heater.setpoint
    heater.setpoint = 4 * sp
    print "New SP",
    print heater.setpoint
    print "Power",
    print heater.power
    heater.setpoint = sp
    print "New SP",
    print heater.setpoint
    print "Power",
    print heater.power


if __name__ == "__main__":
    main()
