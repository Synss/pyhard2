# vim: tw=120
"""Drivers for Amtron CS400 family of controllers.

"""
import unittest
import time
from functools import partial
from operator import mul, div
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


class AmtronHardwareError(drv.HardwareError): pass


class AmtronDriverError(drv.DriverError): pass


def _parse_bits(dct):
    def parser(byte):
        return [v for k, v in dct.items() if k & byte != 0]
    return parser


class CommunicationProtocol(drv.CommunicationProtocol):

    """Communication uses a simple ASCII protocol.

    .. uml::

        group Set
        User    ->  Instrument: :w {byte subsystem}{byte command} {value}
        end

        group Query
        User    ->  Instrument: :r {byte subsystem}{byte command}
        User    <-- Instrument: {echo}
        User    <-- Instrument: :{response}
        User    <-- Instrument: :OK
        end

    """
    errors = dict(A="value is read only",
                  R="value out of range",
                  S="controller in stand-by or manual mode",)

    def __init__(self, socket):
        super(CommunicationProtocol, self).__init__(socket)
        self._socket.baudrate = 19200
        self._socket.timeout = 3
        self._socket.newline = "\r\n"

    def read(self, context):
        assert(not self._socket.inWaiting())
        line = ":r {0:01X}{1:02X}\r".format(context.path[0].index,
                                            context.reader)
        self._socket.write(line)
        self._check_echo(line, self._socket.readline())
        ans = self._socket.readline()
        self._check_status(line, self._socket.readline())
        return int(ans.strip()[1:])  # ":<ANSWER>\r\n"

    def write(self, context):
        assert(not self._socket.inWaiting())
        line = ":w {0:01X}{1:02X} {2:.0f}\r".format(context.path[0].index,
                                                    context.writer,
                                                    context.value)
        self._socket.write(line)
        self._check_echo(line, self._socket.readline())
        self._check_status(line, self._socket.readline())

    @staticmethod
    def _check_echo(line, echo):
        r""" Check for "<ECHO>\r\n". """
        if echo.strip() != line.strip():
            raise AmtronDriverError(
                "Command %r was not echoed, received %r instead" % (line, echo))

    @staticmethod
    def _check_status(line, status):
        r""" Check for ":OK   \r\n" or ":ERR #\r\n". """
        if status.startswith(":OK"):
            return
        elif status.startswith(":ER"):
            raise AmtronHardwareError(
                "Command %r returned error: %r '%s'." %
                (line.strip(), status.strip(),
                 CommunicationProtocol.errors.get(status[4], "unknown error code")))
        else:
            raise AmtronDriverError(
                "Command %r returned unknown error: %r" %
                (line.strip(), status.strip()))


class Subsystem(drv.Subsystem):

    """A `Subsystem` with an index."""

    def __init__(self, index, parent=None):
        super(Subsystem, self).__init__(parent)
        self.index = index


class ControlMode:

    """Enum for control.control_mode

    Attributes:
        CURRENT: Control with current.
        POWER: Control with the power.

    """
    CURRENT = 1
    POWER = 2


class _PowerSubsystem(Subsystem):

    """Power unit A, B, C or D."""

    def __init__(self, index, parent):
        super(_PowerSubsystem, self).__init__(index, parent)
        self.errors = Cmd(0x01, rfunc=_parse_bits(
            {0x0001: "interlock",
             0x0002: "no prim voltage",
             0x0004: "no output voltage",
             0x0008: "internal-malvoltage",
             0x0010: "internal-relay open",
             0x0020: "internal-relay short",
             0x0040: "link failure",
             0x0080: "DC overtemp",
             0x0100: "internal-dcmal",
             0x0200: "overcurrent",
             0x0400: "internal-overpower",
             0x0800: "internal-malcurrent",
             0x1000: "PA overtemp",
             0x2000: "internal error",
             0x4000: "see error 2",  # <--
             0x8000: "command error"}), access=Access.RO)
        self.errors2 = Cmd(0x02, rfunc=_parse_bits(
            {0x0001: "open circuit",
             0x0002: "short circuit",
             0x0008: "internal-nosync",
             0x0010: "internal-nocom1",
             0x0020: "internal-nocom2",
             0x0040: "internal-nocom3",
             0x0200: "firmware config",
             0x0400: "hardware config",
             0x0800: "initialisation error",
             0x1000: "power calibration error"}), access=Access.RO)
        self.warnings = Cmd(0x03, rfunc=_parse_bits(
            {0x0001: "interlock",
             0x0002: "no primary voltage",
             0x0040: "link missing",
             0x0080: "DC/DC temp high",
             0x0100: "internal-dcmal",
             0x1000: "PA temp high",
             0x8000: "internal-wrong cmd"}), access=Access.RO)
        self.current = Cmd(0x0a, rfunc=partial(mul, 0.1), access=Access.RO)
        self.voltage = Cmd(0x0b, rfunc=partial(mul, 0.1), access=Access.RO)
        self.power = Cmd(0x0c, rfunc=partial(mul, 0.1), access=Access.RO)
        self.power_factor = Cmd(0x0d, rfunc=partial(mul, 0.1), wfunc=partial(div, 0.1))  # %
        self.max_current = Cmd(0x0e, rfunc=partial(mul, 0.1), access=Access.RO)
        self.min_voltage = Cmd(0x0f, rfunc=partial(mul, 0.1), access=Access.RO)  # V
        self.max_voltage = Cmd(0x10, rfunc=partial(mul, 0.1), access=Access.RO)  # V

    def _check_error(self):
        err = super(_PowerSubsystem, self)._check_error()
        return err.extend(self.errors2) if "see error 2" in err else err


class CS400(Subsystem):

    """Driver for the Amtron CS400 family of controllers."""

    def __init__(self, socket):
        super(CS400, self).__init__(0x00)
        self.setProtocol(CommunicationProtocol(socket))
        # Main subsystem
        self.errors = Cmd(0x01, rfunc=_parse_bits(
            {0x0080: "CAN guarding timeout",
             0x0100: "laser on timeout",
             0x0200: "firmware config",
             0x0400: "hardware config",
             0x0800: "initialisation failure",
             0x1000: "device overtemp",
             0x8000: "wrong command"}), access=Access.RO)
        self.warnings = Cmd(0x03, rfunc=_parse_bits({0x0080: "startup is delayed"}), access=Access.RO)
        self.configuration = Cmd(0x05, minimum=0x0, maximum=0x8001)
        self.firmware = Cmd(0x07, rfunc=partial(mul, 0.001), access=Access.RO)
        self.operation_mode = Cmd(0x0A, minimum=0, maximum=4)
        self._gate = Cmd(0x0B, minimum=0, maximum=0xffff)
        self._command = Cmd(0x0D, minimum=0, maximum=24)
        self._devstate = Cmd(0x0E, access=Access.RO)
        self.errors_total = Cmd(0x12, access=Access.RO)
        self.warnings_total = Cmd(0x13, access=Access.RO)
        self.timeout_laser_on = Cmd(0x14, minimum=0, maximum=3000, rfunc=partial(mul, 0.1),
                                    wfunc=partial(div, 0.1))  # s
        self.operation_time = Cmd(0x1A, access=Access.RO)  # h
        # Profile subsystem
        self.profile = Subsystem(0x01, self)
        # Parameters, limits and operating modes of the power control system.
        self.control = Subsystem(0x02, self)
        self.control.control_mode = Cmd(0x04, minimum=1, maximum=4)
        self.control.total_current = Cmd(0x05, minimum=0, maximum=3200,
                                         rfunc=partial(mul, 0.1), wfunc=partial(div, 0.1))  # A
        self.control.total_current_meas = Cmd(0x06, rfunc=partial(mul, 0.1), access=Access.RO)  # A
        self.control.total_power = Cmd(0x07, minimum=0, maximum=40000,
                                       rfunc=partial(mul, 0.1), wfunc=partial(div, 0.1))  # W
        self.control.total_power_meas = Cmd(0x08, rfunc=partial(mul, 0.1), access=Access.RO)  # W
        self.control.total_power_calc = Cmd(0x0A, rfunc=partial(mul, 0.1), access=Access.RO)  # W
        self.control.pulse_duration = Cmd(0x1A, minimum=10, maximum=65000)
        self.control.pulse_pause = Cmd(0x1B, minimum=0, maximum=65000)
        # Laser's measure and calibration values.
        self.laser = Subsystem(0x05, self)
        self.laser.errors = Cmd(0x01, rfunc=_parse_bits(
            {0x0001: "head humidity too high",
             0x0002: "laser fiber broken",
             0x0004: "laser fiber shortened",
             0x0008: "shutter error",
             0x0010: "fiber not plugged",
             0x0040: "interlock head on",
             0x0080: "interlock head wire",
             0x0400: "config hardware error",
             0x0800: "laser temp too high",
             0x1000: "laser power dev too high"}),
            access=Access.RO)
        self.laser.warnings = Cmd(0x03, rfunc=_parse_bits(
            {0x0001: "head humidity high",
             0x0040: "interlock head on",
             0x0100: "laser ervice interval",
             0x0200: "laser temp too low",
             0x0400: "laser temp high",
             0x0800: "laser temp too high"}),
            access=Access.RO)
        self.laser.configuration = Cmd(0x05, minimum=0x0, maximum=0xfff)
        self.laser._serial_number_high = Cmd(0x07, access=Access.RO)
        self.laser._serial_number_low = Cmd(0x08, access=Access.RO)
        self.laser.on_time = Cmd(0x09, access=Access.RO)
        self.laser.service_interval = Cmd(0x0A, access=Access.RO)
        self.laser.temperature = Cmd(0x0C, rfunc=partial(mul, 0.1), access=Access.RO)  # degC
        self.laser.power = Cmd(0x0D, rfunc=partial(mul, 0.1), access=Access.RO)  # W
        self.laser.head_humidity = Cmd(0x0F, rfunc=partial(mul, 0.1), access=Access.RO)
        # Interface configurations and states.
        self.interface = Subsystem(0x06, self)
        self.interface.errors = Cmd(0x01, rfunc=_parse_bits(
            {0x0001: "emergency stop",
            0x0002: "emergency stop wire",
            0x0004: "emergency stop remote terminal",
            0x0008: "emergency wire remote terminal",
            0x0010: "emergency stop external",
            0x0020: "emergency stop external wire",
            0x0040: "interlock external",
            0x0080: "interlock external wire",
            0x0100: "link error",
            0x0200: "emergency stop SPI",
            0x0400: "warn light(s) error",
            0x1000: "cooler temp",
            0x2000: "cooler flow"}), access=Access.RO)
        self.interface.warnings = Cmd(0x03, rfunc=_parse_bits(
            {0x0040: "interlock external",
            0x0400: "warn light(s) warning",
            0x1000: "cooler temp",
            0x2000: "cooler flow"}), access=Access.RO)
        self.interface.io_config = Cmd(0x05, minimum=0x0, maximum=0xffff)
        self.interface.io_config_OEM = Cmd(0x06, access=Access.RO)
        self.interface.io_state = Cmd(0x07, access=Access.RO)
        self.interface.io_digital_in = Cmd(0x09)
        self.interface.io_digital_out = Cmd(0x0a, minimum=0x0, maximum=0xffff)
        self.interface.pilot_beam_intensity = Cmd(0x0b, minimum=1, maximum=10)
        self.interface.PWM_input_offset = Cmd(0x0c, access=Access.RO)
        self.interface.PWM_input_slope = Cmd(0x0d, access=Access.RO)
        # Cooler contorller specific registers.
        self.cooler = Subsystem(0x07, self)
        self.cooler._errors1 = Cmd(0x01, access=Access.RO)
        self.cooler._errors2 = Cmd(0x02, access=Access.RO)
        self.cooler._warnings = Cmd(0x03, access=Access.RO)
        # Power subsystem
        self.power = _PowerSubsystem(0x0a, self)
        # Handle main.CMD, main.DEVSTATE, and main.GATE.
        self.command = drv.Subsystem(self)
        self.command.setProtocol(drv.CommandCallerProtocol())
        self.command.clear_errors = Cmd(partial(self._command.write, 1), access=Access.WO)
        self.command.laser_state = Cmd(self.__get_laser_state, self.__set_laser_state)
        self.command.gate_state = Cmd(self.__get_gate_state, self.__set_gate_state)
        self.command.is_ready = Cmd(self.__is_ready, access=Access.RO)
        self.command.is_laser_enabled = Cmd(self.__is_laser_enabled, access=Access.RO)
        self.command.is_warning_present = Cmd(self.__is_warning_present, access=Access.RO)
        self.command.is_error_present = Cmd(self.__is_error_present, access=Access.RO)

    def __set_laser_state(self, enable):
        if enable:
            self.clear_errors()
            self._command.write(3)  # power on/laser disabled
            time.sleep(1.0)                    # delay required
            self._command.write(4)  # laser enabled
        else:
            self._command.write(3)  # power on/laser disabled
            self._command.write(2)  # power off

    def __get_laser_state(self):
        return bool(self._devstate.read() & 0x0002)

    def __set_gate_state(self, state):
        self._gate.write(0x8b6c if state else 0x0000)

    def __get_gate_state(self):
        return bool(self._devstate.read() & 0x0004)

    def __is_ready(self):
        return bool(self._devstate.read() & 0x0001)

    def __is_laser_enabled(self):
        return bool(self._devstate.read() & 0x0002)

    def __is_warning_present(self):
        return bool(self._devstate.read() & 0x0010)

    def __is_error_present(self):
        return bool(self._devstate.read() & 0x0020)


class TestCS400(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {":r 007\r": ":r 007\r\n:1234\r\n:OK   \r\n",
                      ":r 00E\r": ":r 00E\r\n:0\r\n:OK   \r\n",
                      ":r 60B\r": ":r 60B\r\n:5\r\n:OK   \r\n",
                      ":w 60B 5\r": ":w 60B 5\r\n:OK   \r\n"}
        self.i = CS400(socket)

    def test_root_subsystem(self):
        self.assertEqual(self.i.firmware.read(), 1.234)

    def test_command_subsystem(self):
        self.assertFalse(self.i.command.is_ready.read())

    def test_nested_subsystem(self):
        self.assertEqual(self.i.interface.pilot_beam_intensity.read(), 5)

    def test_write(self):
        self.i.interface.pilot_beam_intensity.write(5)


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logger = logging.getLogger("pyhard2")
    logger.setLevel(logging.DEBUG)
    unittest.main()
