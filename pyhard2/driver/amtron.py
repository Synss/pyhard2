"""
Amtron drivers
==============

Drivers for Amtron CS400 family of controllers.


Communication uses a simple ASCII protocol:

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

import time
import pyhard2.driver as drv
Param = drv.Parameter


class AmtronHardwareError(drv.HardwareError): pass


class AmtronDriverError(drv.DriverError): pass


class ControlMode:
    """ Enum for control.control_mode. """

    CURRENT = 1
    POWER = 2


def scalemul(factor):
    def parser(x):
        return x * factor
    return parser

def scalediv(factor):
    def parser(x):
        return x / factor
    return parser

def parse_bits(dct):
    def parser(byte):
        return [v for k, v in dct.items() if k & byte != 0]
    return parser


class Protocol(drv.SerialProtocol):

    """ASCII protocol."""

    errors = dict(A="value is read only",
                  R="value out of range",
                  S="controller in stand-by or manual mode",
                 )

    def __init__(self, socket, async):
        super(Protocol, self).__init__(
            socket,
            async,
            fmt_read=":r {subsys[index]:01X}{param[getcmd]:02X}\r",
            fmt_write=":w {subsys[index]:01X}{param[getcmd]:02X} {val:.0f}\r",
        )

    def _encode_read(self, subsys, param):
        assert(not self.socket.inWaiting())
        cmd = self._fmt_cmd_read(subsys, param)
        self.socket.write(cmd)
        self._check_echo(cmd, self.socket.readline())
        ans = self.socket.readline()
        self._check_status(cmd, self.socket.readline())
        return int(ans.strip()[1:])  # ":<ANSWER>\r\n"

    def _encode_write(self, subsys, param, val):
        assert(not self.socket.inWaiting())
        cmd = self._fmt_cmd_write(subsys, param, val)
        self.socket.write(cmd)
        self._check_echo(cmd, self.socket.readline())
        self._check_status(cmd, self.socket.readline())

    @staticmethod
    def _check_echo(cmd, echo):
        r""" Check for "<ECHO>\r\n". """
        if echo.strip() != cmd.strip():
            raise AmtronDriverError(
                "Command %r was not echoed, received %r instead" % (cmd, echo))

    @staticmethod
    def _check_status(cmd, status):
        r""" Check for ":OK   \r\n" or ":ERR #\r\n". """
        if status.startswith(":OK"):
            return
        elif status.startswith(":ER"):
            raise AmtronHardwareError(
                "Command %r returned error: %r '%s'." %
                (cmd.strip(), status.strip(),
                 Protocol.errors.get(status[4], "unknown error code")))
        else:
            raise AmtronDriverError(
                "Command %r returned unknown error: %r" %
                (cmd.strip(), status.strip()))


class Subsystem(drv.Subsystem):

    """
    Subsystem with an index.

    Parameters
    ----------
    instrument
    index : hexadecimal number

    """

    def __init__(self, protocol, index):
        super(Subsystem, self).__init__(protocol)
        self.index = index

    def __repr__(self):
        return "%s(protocol=%r, index=%r)" % (
            self.__class__.__name__, self.protocol, self.index)


class MainSubsystem(Subsystem):

    """Main registers with superordinated functions."""

    errors = Param(0x01, getter_func=parse_bits(
        {0x0080: "CAN guarding timeout",
         0x0100: "laser on timeout",
         0x0200: "firmware config",
         0x0400: "hardware config",
         0x0800: "initialisation failure",
         0x1000: "device overtemp",
         0x8000: "wrong command"}), read_only=True)
    warnings = Param(0x03, getter_func=parse_bits(
        {0x0080: "startup is delayed"}), read_only=True)
    configuration = Param(0x05, minimum=0x0, maximum=0x8001)
    firmware = Param(0x07, getter_func=scalemul(0.001), read_only=True)
    operation_mode = Param(0x0A, minimum=0, maximum=4)
    _gate = Param(0x0B, minimum=0, maximum=0xffff)
    _command = Param(0x0D, minimum=0, maximum=24)
    _devstate = Param(0x0E, read_only=True)
    errors_total = Param(0x12, read_only=True)
    warnings_total = Param(0x13, read_only=True)
    timeout_laser_on = Param(0x14, minimum=0, maximum=3000,
                             getter_func=scalemul(0.1),
                             setter_func=scalediv(0.1))  # s
    operation_time = Param(0x1A, read_only=True)  # h


class CommandSubsystem(drv.MetaSubsystem):

    """ Handle main.CMD, main.DEVSTATE, and main.GATE. """

    def __clear_errors(self):
        self._subsystem._command = 1

    clear_errors = drv.Action(__clear_errors)

    def __set_laser_state(self, enable):
        if enable:
            self.clear_errors()
            self._subsystem._command = 3  # power on/laser disabled
            time.sleep(1.0)               # delay required
            self._subsystem._command = 4  # laser enabled
        else:
            self._subsystem._command = 3  # power on/laser disabled
            self._subsystem._command = 2  # power off

    def __get_laser_state(self):
        return bool(self._subsystem._devstate & 0x0002)

    laser_state = drv.Parameter(__get_laser_state, __set_laser_state)

    def __set_gate_state(self, state):
        self._subsystem._gate = 0x8b6c if state else 0x0000

    def __get_gate_state(self):
        return bool(self._subsystem._devstate & 0x0004)

    gate_state = drv.Parameter(__get_gate_state, __set_gate_state)

    def __is_ready(self):
        return bool(self._subsystem._devstate & 0x0001)

    is_ready = Param(__is_ready, read_only=True)

    def __is_laser_enabled(self):
        return bool(self._subsystem._devstate & 0x0002)

    is_laser_enabled = Param(__is_laser_enabled, read_only=True)

    def __is_warning_present(self):
        return bool(self._subsystem._devstate & 0x0010)

    is_warning_present = Param(__is_warning_present, read_only=True)

    def __is_error_present(self):
        return bool(self._subsystem._devstate & 0x0020)

    is_error_present = Param(__is_error_present, read_only=True)


class ProfileSubsystem(Subsystem):

    """Sampling points for profile mode."""


class ControlSubsystem(Subsystem):

    """
    Parameters, limits and operating modes of the power control system.
    """

    control_mode = Param(0x04, minimum=1, maximum=4)
    total_current = Param(0x05, minimum=0, maximum=3200,
                          getter_func=scalemul(0.1),
                          setter_func=scalediv(0.1))  # A
    total_current_meas = Param(0x06, getter_func=scalemul(0.1),
                               read_only=True)  # A
    total_power = Param(0x07, minimum=0, maximum=40000,
                        getter_func=scalemul(0.1),
                        setter_func=scalediv(0.1))  # W
    total_power_meas = Param(0x08, getter_func=scalemul(0.1),
                             read_only=True)  # W
    total_power_calc = Param(0x0A, getter_func=scalemul(0.1),
                             read_only=True)  # W
    pulse_duration = Param(0x1A, minimum=10, maximum=65000)
    pulse_pause = Param(0x1B, minimum=0, maximum=65000)


class LaserSubsystem(Subsystem):

    """Laser's measure and calibration values."""

    errors = Param(0x01, getter_func=parse_bits(
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
        read_only=True)
    warnings = Param(0x03, getter_func=parse_bits(
        {0x0001: "head humidity high",
         0x0040: "interlock head on",
         0x0100: "laser ervice interval",
         0x0200: "laser temp too low",
         0x0400: "laser temp high",
         0x0800: "laser temp too high"}),
        read_only=True)
    configuration = Param(0x05, minimum=0x0, maximum=0xfff)
    _serial_number_high = Param(0x07, read_only=True)
    _serial_number_low = Param(0x08, read_only=True)
    on_time = Param(0x09, read_only=True)
    service_interval = Param(0x0A, read_only=True)
    temperature = Param(0x0C, getter_func=scalemul(0.1), read_only=True)  # degC
    power = Param(0x0D, getter_func=scalemul(0.1), read_only=True)  # W
    head_humidity = Param(0x0F, getter_func=scalemul(0.1), read_only=True)

    @property
    def serial_number(self):
        return ''.join((self._serial_number_high, self._serial_number_low))


class InterfaceSubsystem(Subsystem):

    """Interface configurations and states."""

    errors = Param(0x01, getter_func=parse_bits(
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
         0x2000: "cooler flow"}), read_only=True)
    warnings = Param(0x03, getter_func=parse_bits(
        {0x0040: "interlock external",
         0x0400: "warn light(s) warning",
         0x1000: "cooler temp",
         0x2000: "cooler flow"}), read_only=True)
    io_config = Param(0x05, minimum=0x0, maximum=0xffff)
    io_config_OEM = Param(0x06, read_only=True)
    io_state = Param(0x07, read_only=True)
    io_digital_in = Param(0x09)
    io_digital_out = Param(0x0a, minimum=0x0, maximum=0xffff)
    pilot_beam_intensity = Param(0x0b, minimum=1, maximum=10)
    PWM_input_offset = Param(0x0c, read_only=True)
    PWM_input_slope = Param(0x0d, read_only=True)


class CoolerSubsystem(Subsystem):

    """Cooler contorller specific registers."""

    _errors1 = Param(0x01, read_only=True)
    _errors2 = Param(0x02, read_only=True)
    _warnings = Param(0x03, read_only=True)


class PowerSubsystem(Subsystem):

    """Power unit A, B, C or D."""

    def _check_error(self):
        err = super(PowerSubsystem, self)._check_error()
        return err.extend(self.errors2) if "see error 2" in err else err

    errors = Param(0x01, getter_func=parse_bits(
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
         0x8000: "command error"}), read_only=True)
    errors2 = Param(0x02, getter_func=parse_bits(
        {0x0001: "open circuit",
         0x0002: "short circuit",
         0x0008: "internal-nosync",
         0x0010: "internal-nocom1",
         0x0020: "internal-nocom2",
         0x0040: "internal-nocom3",
         0x0200: "firmware config",
         0x0400: "hardware config",
         0x0800: "initialisation error",
         0x1000: "power calibration error"}), read_only=True)
    warnings = Param(0x03, getter_func=parse_bits(
        {0x0001: "interlock",
         0x0002: "no primary voltage",
         0x0040: "link missing",
         0x0080: "DC/DC temp high",
         0x0100: "internal-dcmal",
         0x1000: "PA temp high",
         0x8000: "internal-wrong cmd"}), read_only=True)
    current = Param(0x0a, getter_func=scalemul(0.1), read_only=True)  # A
    voltage = Param(0x0b, getter_func=scalemul(0.1), read_only=True)  # V
    power = Param(0x0c, getter_func=scalemul(0.1), read_only=True)  # W
    power_factor = Param(0x0d, getter_func=scalemul(0.1),
                               setter_func=scalediv(0.1))  # %
    max_current = Param(0x0e, getter_func=scalemul(0.1), read_only=True)  # A
    min_voltage = Param(0x0f, getter_func=scalemul(0.1), read_only=True)  # V
    max_voltage = Param(0x10, getter_func=scalemul(0.1), read_only=True)  # V


class CS400(drv.Instrument):

    """
    Instrument for the Amtron CS400 family of controllers.
    """

    def __init__(self, socket, async=False):
        super(CS400, self).__init__()

        socket.baudrate = 19200
        socket.timeout = 3
        socket.newline = "\r\n"

        protocol = Protocol(socket, async)

        self._main = MainSubsystem(protocol, 0x00)
        self.command = CommandSubsystem(
            drv.ProtocolLess(None, async=False), self._main)
        self.profile = ProfileSubsystem(protocol, 0x01)
        self.control = ControlSubsystem(protocol, 0x02)
        self.laser = LaserSubsystem(protocol, 0x05)
        self.interface = InterfaceSubsystem(protocol, 0x06)
        self.cooler = CoolerSubsystem(protocol, 0x07)
        self.power = PowerSubsystem(protocol, 0x0a)
        self.main = self._main

