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

import pyhard2.driver as drv
Param = drv.Parameter


class AmtronHardwareError(drv.HardwareError): pass


class AmtronDriverError(drv.DriverError): pass


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

    def __init__(self, socket, async):
        super(Protocol, self).__init__(
            socket,
            async,
            fmt_read=":r {subsys[index]:02X}{param[getcmd]:02X}\r",
            fmt_write=":w {subsys[index]:02X}{param[getcmd]:02X} {val}\r",
        )

    def _encode_read(self, subsys, param):
        cmd = self._fmt_cmd_read(subsys, param)
        self.socket.write(cmd)
        self.socket.readline()                   # "ECHO<CR>"
        ans = self.socket.readline()             # ":ANSWER<CR>"
        status = self.socket.readline().strip()  # ":OK<CR>" or ":ERR #<CR>"
        if status.startswith(":OK"):
            return int(ans.strip()[1:])
        elif status.startswith(":ERR"):
            raise AmtronHardwareError(
                "Command %s returned error: %s" %
                (cmd.strip(), status.strip()))
        else:
            raise AmtronDriverError(
                "Command %s returned unknown error: %s" %
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
         0x8000: "wrong command"}))
    warnings = Param(0x03, getter_func=parse_bits(
        {0x0080: "startup is delayed"}))
    configuration = Param(0x05, minimum=0x0, maximum=0x8001)
    firmware = Param(0x07, getter_func=scalemul(0.001))  # * 0.001
    operation_mode = Param(0x0A, minimum=0, maximum=4)
    #gate = Param(0x0B, minimum=0x0, maximum=0xffff)

    @property
    def gate(self):
        return self.query(0x0B) == 0x8B6C

    @gate.setter
    def gate(self, set_open):
        return self.set(0x0B, 0x8B6C if set_open else 0x0000)

    device_state = Param(0x0E)
    errors_total = Param(0x12)
    warnings_total = Param(0x13)
    timeout_laser_on = Param(0x14, minimum=0, maximum=3000,
                             getter_func=scalemul(0.1),
                             setter_func=scalediv(0.1))  # s
    operation_time = Param(0x1A)  # h


class ProfileSubsystem(Subsystem):

    """Sampling points for profile mode."""


class ControlSubsystem(Subsystem):

    """
    Parameters, limits and operating modes of the power control system.
    """

    control_mode = Param(0x04, minimum=1, maximum=4)
    set_total_current = Param(0x05, minimum=0, maximum=3200,
                              getter_func=scalemul(0.1),
                              setter_func=scalediv(0.1))  # A
    total_current = Param(0x06, getter_func=scalemul(0.1))  # A
    set_total_power = Param(0x07, minimum=0, maximum=40000,
                            getter_func=scalemul(0.1),
                            setter_func=scalediv(0.1))  # W
    total_power_meas = Param(0x08, getter_func=scalemul(0.1))  # W
    total_power_calc = Param(0x0A, getter_func=scalemul(0.1))  # W
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
         0x1000: "laser power dev too high"}))
    warnings = Param(0x03, getter_func=parse_bits(
        {0x0001: "head humidity high",
         0x0040: "interlock head on",
         0x0100: "laser ervice interval",
         0x0200: "laser temp too low",
         0x0400: "laser temp high",
         0x0800: "laser temp too high"}))
    configuration = Param(0x05, minimum=0x0, maximum=0xfff)
    _serial_number_high = Param(0x07)
    _serial_number_low = Param(0x08)
    on_time = Param(0x09)
    service_interval = Param(0x0A)
    temperature = Param(0x0C, getter_func=scalemul(0.1))  # degC
    power = Param(0x0D, getter_func=scalemul(0.1))  # W
    head_humidity = Param(0x0F, getter_func=scalemul(0.1))

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
         0x2000: "cooler flow"}))
    warnings = Param(0x03, getter_func=parse_bits(
        {0x0040: "interlock external",
         0x0400: "warn light(s) warning",
         0x1000: "cooler temp",
         0x2000: "cooler flow"}))
    io_config = Param(0x05, minimum=0x0, maximum=0xffff)
    io_config_OEM = Param(0x06)
    io_state = Param(0x07)
    io_digital_in = Param(0x09)
    io_digital_out = Param(0x0a, minimum=0x0, maximum=0xffff)
    pilot_beam_intensity = Param(0x0b, minimum=1, maximum=10)
    PWM_input_offset = Param(0x0c)
    PWM_input_slope = Param(0x0d)


class CoolerSubsystem(Subsystem):

    """Cooler contorller specific registers."""

    _errors1 = Param(0x01)
    _errors2 = Param(0x02)
    _warnings = Param(0x03)


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
         0x8000: "command error"}))
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
         0x1000: "power calibration error"}))
    warnings = Param(0x03, getter_func=parse_bits(
        {0x0001: "interlock",
         0x0002: "no primary voltage",
         0x0040: "link missing",
         0x0080: "DC/DC temp high",
         0x0100: "internal-dcmal",
         0x1000: "PA temp high",
         0x8000: "internal-wrong cmd"}))
    current = Param(0x0a, getter_func=scalemul(0.1))  # A
    voltage = Param(0x0b, getter_func=scalemul(0.1))  # V
    power = Param(0x0c, getter_func=scalemul(0.1))  # W
    power_fraction = Param(0x0d, getter_func=scalemul(0.1))  # %
    max_current = Param(0x0e, getter_func=scalemul(0.1))  # A
    min_voltage = Param(0x0f, getter_func=scalemul(0.1))  # V
    max_voltage = Param(0x10, getter_func=scalemul(0.1))  # V


class CS400(drv.Instrument):

    """
    Instrument for the Amtron CS400 family of controllers.
    """

    def __init__(self, socket, async=False):
        super(CS400, self).__init__()

        socket.baudrate = 19200
        socket.timeout = 3
        socket.newline = "\r"

        protocol = Protocol(socket, async)

        self.main = MainSubsystem(protocol, 0x00)
        self.profile = ProfileSubsystem(protocol, 0x01)
        self.control = ControlSubsystem(protocol, 0x02)
        self.laser = LaserSubsystem(protocol, 0x05)
        self.interface = InterfaceSubsystem(protocol, 0x06)
        self.cooler = CoolerSubsystem(protocol, 0x07)
        self.power = PowerSubsystem(protocol, 0x0a)

