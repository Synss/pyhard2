"""
Pfeiffer drivers
================

Drivers for the Pfeiffer TPG 256 A MaxiGauge controller.

"""

import logging
import ascii

import pyhard2.driver as drv
Param = drv.Parameter


class PfeifferHardwareError(drv.HardwareError): pass


class PfeifferDriverError(drv.DriverError): pass


class Protocol(drv.SerialProtocol):

    """
    The protocol used is close to ANSI X3.

    .. uml::

        User    ->  Instrument: {query}
        User    <-- Instrument: ACK
        User    ->  Instrument: ENQ
        User    <-- Instrument: {answer}
    
    """

    def __init__(self, socket, async, fmt_read, fmt_write):
        super(Protocol, self).__init__(socket, async, fmt_read, fmt_write)

    def _encode_read(self, subsys, param):
        cmd = self._fmt_cmd_read(subsys, param) + self.socket.newline
        self.socket.write(cmd)             # master: "MNEMONIC <CR><LF>"
        ack = self.socket.readline()       # remote: "ACK<CR><LF>"
        self._check_error(cmd, ack)
        ENQ = chr(ascii.ENQ) + self.socket.newline
        self.socket.write(ENQ)             # master: "ENQ<CR><LF>"
        ans = self.socket.readline()       # remote: "VALUE <CR><LF>"
        return ans.strip()

    def _encode_write(self, subsys, param, val):
        cmd = self._fmt_cmd_write(subsys, param, val)
        self.socket.write(cmd)             # master: "MNEMONIC VAL <CR><LF>"
        ack = self.socket.readline()       # remote: "ACK<CR><LF>"
        self._check_error(cmd, ack)

    @staticmethod
    def _check_error(cmd, ack):
        if ack.startswith(chr(ascii.NAK)):
            raise drv.PfeifferHardwareError(
                "Command %s not acknowledged." % cmd.strip())
        elif not ack.startswith(chr(ascii.ACK)):
            raise drv.PfeifferDriverError(
                "Command %s raised unknown error." % cmd.strip())


def parse_pressure(msg):
    """Parser for measurement:PRx."""
    status_msg = {0: "Measurement data okay",
                  1: "Underrange",
                  2: "Overrange",
                  3: "Sensor error",
                  4: "Sensor off",
                  5: "No sensor",
                  6: "Identification error"}
    # ans fmt: "x,x.xxxEsx\r\n"
    status, value = msg.split(",")
    status = int(status)
    if status != 0:
        logging.info("Sensor status: %s" % status_msg[status])
        raise PfeifferHardwareError("Sensor returned: %s" % status_msg[status])
    else:
        return float(value)


def parse_error(ans):

    """Parser for errors."""

    error1 = {0: "No error",
              1: "Watchdog has responded",
              2: "Task fail error",
              4: "IDCX idle error",
              16: "EPROM error",
              32: "RAM error",
              64: "EEPROM error",
              128: "Key error",
              4096: "Syntax error",
              8192: "Inadmissible parameter",
              16384: "No hardware",
              32768: "Fatal error"}
    error2 = {0: "No error",
              1: "Sensor 1: measurement error",
              2: "Sensor 2: measurement error",
              4: "Sensor 3: measurement error",
              8: "Sensor 4: measurement error",
              16: "Sensor 5: measurement error",
              32: "Sensor 6: measurement error",
              512: "Sensor 1: identification error",
              1024: "Sensor 2: identification error",
              2048: "Sensor 3: identification error",
              4096: "Sensor 4: identification error",
              8192: "Sensor 5: identification error",
              16384: "Sensor 6: identification error"}
    e1, e2 = ans.split(",")
    e1, e2 = int(e1), int(e2)
    if (e1, e2) != (0, 0):
        err = ([v for k, v in error1.items() if k & e1 != 0],
               [v for k, v in error2.items() if k & e2 != 0])
        raise drv.HardwareError(err)


class GaugeSubsystem(drv.Subsystem):

    """Gauge subsystem.

    .. warning::

        Only the parameters `pressure` and `measure` are implemented.

    Parameters
    ----------
    instrument
    node : int
        Sensor identifier.
    
    """

    # Measurement
    # SEN bool
    # SCx
    # PRx
    pressure = Param("PR", read_only=True, getter_func=parse_pressure)
    measure = Param("PR", read_only=True, getter_func=parse_pressure)

    # DCD
    # CID

    # Display
    # UNI
    # DCB
    # DCC
    # DCS

    # Switching
    # SPx
    # SPS
    # PUC

    # Parameters
    # LOC
    # FIL
    # CAx
    # OFC
    # FSR
    # DGS
    # SAV

    # Interfaces
    # RSX
    # BAU
    # NAD


class ControllerSubsystem(drv.Subsystem):

    """Controller subsystem.

    .. warning::

        Only the parameters `errors` and `unit` are implemented.

    """

    errors = Param("ERR", read_only=True, getter_func=parse_error)
    unit = Param("UNI", read_only=True, getter_func=lambda msg: 
                 {0: "mbar", 1: "Torr", 2: "Pascal"}[int(msg)])


class Maxigauge(drv.Instrument):

    """Driver for Pfeiffer Maxigauge."""

    def __init__(self, socket, async, node):
        super(Maxigauge, self).__init__()
        socket.timeout = 5.0
        socket.newline = "\r\n"
        gaugeProtocol = Protocol(
            socket,
            async,
            fmt_read="{param[getcmd]}{protocol[node]}",
            fmt_write="{param[setcmd]}{protocol[node]} {val}")
        gaugeProtocol.node = node
        self.main = GaugeSubsystem(gaugeProtocol)
        controllerProtocol = Protocol(
            socket,
            async,
            fmt_read="{param[getcmd]}",
            fmt_write="{param[setcmd]}")
        self.controller = ControllerSubsystem(controllerProtocol)

