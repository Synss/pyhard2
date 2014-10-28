"""Drivers for Watlow Series 988 family of controllers.

Note:
    The XON/XOFF protocol is implemented.

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


class WatlowHardwareError(drv.HardwareError): pass


class WatlowDriverError(drv.DriverError): pass


class XonXoffProtocol(drv.CommunicationProtocol):

    """Communication using the XON/XOFF protocol follows:

    .. uml::

        group Set
        User    ->  Instrument: "= {mnemonic} {value}"
        User    <-- Instrument: XOFF
        User    <-- Instrument: XON
        end

        group Query
        User    ->  Instrument: "? {mnemonic}"
        User    <-- Instrument: XOFF
        User    <-- Instrument: XON{value}
        end

    """
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

    def __init__(self, socket):
        super(XonXoffProtocol, self).__init__(socket)
        self._socket.timeout = 5.0
        self._socket.newline = "\r"

    def _xonxoff(self):
        xonxoff = self._socket.read(2)
        if not xonxoff == "\x13\x11":
            raise WatlowDriverError("Expected XON/XOFF (%r) got %r instead."
                                    % ("\x13\x11", xonxoff))

    def read(self, context):
        line = "? {reader}\r".format(reader=context.reader)
        self._socket.write(line)
        self._xonxoff()
        ans = self._socket.readline()
        self._check_error(line)     # check for error
        try:
            return float(ans.strip())  # unicode to number
        except ValueError:
            if ans.strip() == "-----":
                raise WatlowHardwareError("Unplugged thermocouple.")
            else:
                raise

    def write(self, context):
        line = "= {writer} {value}\r".format(writer=context.writer,
                                             value=context.value)
        self._socket.write(line)
        self._xonxoff()
        self._check_error(line)     # check for error

    def _check_error(self, line):
        self._socket.write("? ER2\r")
        self._xonxoff()
        err_code = self._socket.readline()
        if not err_code.startswith("0"):
            try:
                err = XonXoffProtocol._err[int(err_code)]
                raise drv.HardwareError(
                    "Command %r returned error: %s" %
                    (line, err))
            except KeyError:
                raise WatlowDriverError(
                    "Command %r returned unkwnown error: %s" %
                    (line, err_code))


class ModbusProtocol(drv.CommunicationProtocol):

    def __init__(self, socket):
        raise NotImplementedError

    def __repr__(self):
        return "%s(socket=%r)" % (self.__class__.__name__, self.socket)


def _fahrenheit2celsius(x):
    """Conversion function."""
    return (float(x) - 32.0) / 1.8


def subsystemFromCsv(subsystem, csvtable, cmd_suffix=""):
    for line in csvtable.splitlines():
        if line.strip():
            cmd_name, cmd, minimum, maximum = line.split()
            setattr(subsystem, cmd_name,
                    Cmd("".join((cmd, str(cmd_suffix))), 
                        minimum=int(minimum), maximum=int(maximum)))


class Series988(drv.Subsystem):

    """Driver for the Watlow Series 988 family of controllers.

    .. graphviz:: gv/Series988.txt

    """
    def __init__(self, socket):
        super(Series988, self).__init__()
        self.setProtocol(XonXoffProtocol(socket))
        self.setpoint = Cmd("SP1", minimum=-250, maximum=9999)
        self.power = Cmd("PWR", access=Access.RO, doc="power output %")
        self.temperature1 = Cmd("C1", minimum=-250, maximum=9999,
                                access=Access.RO, doc="input value 1")
        self.temperature2 = Cmd("C2", minimum=-250, maximum=9999,
                                access=Access.RO, doc="input value 2")
        # Subsystems
        self.setup = drv.Subsystem(self)
        setup_output_table = (
            # name          cmd     minimum     maximum
            """
            action          OT      0           1
            process_range   PRC     0           4
            hysteresis      HYS     0           999
            """)
        self.setup.output1 = drv.Subsystem(self.setup)
        self.setup.output2 = drv.Subsystem(self.setup)
        self.setup.global_ = drv.Subsystem(self.setup)
        subsystemFromCsv(self.setup.output1, setup_output_table, 1)
        subsystemFromCsv(self.setup.output2, setup_output_table, 2)
        subsystemFromCsv(self.setup.global_,
            # name          cmd     minimum     maximum
            """
            ramp_init   RP      0           2
            ramp_rate   RATE    0           9999
            """)
        self.setup.communication = drv.Subsystem(self.setup)
        self.operation = drv.Subsystem(self)
        self.operation.system = drv.Subsystem(self.operation)
        self.operation.system.setpoint2 = Cmd("SP2")
        self.operation.pid = drv.Subsystem(self.operation)
        self.operation.pid.a1 = drv.Subsystem(self.operation.pid)
        self.operation.pid.a2 = drv.Subsystem(self.operation.pid)
        self.operation.pid.b1 = drv.Subsystem(self.operation.pid)
        self.operation.pid.b2 = drv.Subsystem(self.operation.pid)
        for subsystem, pid_unit in ((self.operation.pid.a1, "1A"),
                                    (self.operation.pid.a2, "2A"),
                                    (self.operation.pid.b1, "1B"),
                                    (self.operation.pid.b2, "2B")):
            for cmd_name, cmd in (("gain", "PB"),
                                  ("integral", "IT"),
                                  ("derivative", "DE")):
                setattr(subsystem, cmd_name,
                        Cmd("".join((cmd, str(pid_unit))),
                            rfunc=float))
        self.factory = drv.Subsystem(self)
        self.factory.lockout = drv.Subsystem(self.factory)
        self.factory.diagnostic = drv.Subsystem(self.factory)
        self.factory.diagnostic.test_data = Cmd("DATE")
        self.factory.diagnostic.software_revision = Cmd("SOFT")
        self.factory.diagnostic.ambient_temperature = Cmd("AMB",
                                rfunc=_fahrenheit2celsius)
        self.factory.calibration = drv.Subsystem(self.factory)


class TestSeries988(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {"? SP1\r": "\x13\x1125\r",
                      "? PWR\r": "\x13\x115\r",
                      "? ER2\r": "\x13\x110\r",
                      "? AMB\r": "\x13\x1172\r",
                      "= SP1 32\r": "\x13\x11",
                      "= PB1A 12\r": "\x13\x11"
                     }
        self.i = Series988(socket)

    def test_root_subsystem(self):
        self.assertEqual(self.i.setpoint.read(), 25)
        self.assertEqual(self.i.power.read(), 5)

    def test_nested_subsystem(self):
        self.assertAlmostEqual(
            self.i.factory.diagnostic.ambient_temperature.read(), 22.22, 2)

    def test_write(self):
        self.i.setpoint.write(32)

    def test_nested_write(self):
        self.i.operation.pid.a1.gain.write(12)


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logger = logging.getLogger("pyhard2")
    logger.setLevel(logging.DEBUG)
    unittest.main()
