"""Drivers for the Pfeiffer TPG 256 A MaxiGauge controller.

"""
import unittest
import logging
logging.basicConfig()
from . import ascii

import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


class PfeifferHardwareError(drv.HardwareError): pass


class PfeifferDriverError(drv.DriverError): pass


def _parse_pressure(msg):
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
        logger = logging.getLogger(__name__)
        logger.info("Sensor status: %s" % status_msg[status])
        raise PfeifferHardwareError("Sensor returned: %s" % status_msg[status])
    else:
        return float(value)


def _parse_error(ans):

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


class CommunicationProtocol(drv.CommunicationProtocol):

    """Driver for the Pfeiffer Maxigauge.

    The protocol used is similar to ANSI X3.

    .. uml::

        User    ->  Instrument: {query}
        User    <-- Instrument: ACK
        User    ->  Instrument: ENQ
        User    <-- Instrument: {answer}
    
    """
    def __init__(self, socket):
        super().__init__(socket)
        self._socket.timeout = 5.0
        self._socket.newline = "\r\n"

    def read(self, context):
        line = "{reader}{node}\r\n".format(reader=context.reader,
                                           node=context.node
                                           if context.node is not None else "")
        self._socket.write(line)        # master: "MNEMONIC <CR><LF>
        ack = self._socket.readline()   # remote: "ACK<CR><LF>"
        self._check_error(line, ack)
        self._socket.write("%c\r\n" % ascii.ENQ)    # master: "ENQ<CR><LF>"
        ans = self._socket.readline()   # remote: "VALUE <CR><LF>"
        return ans.strip()

    def write(self, context):
        line = "{writer}{node} {value}\r\n".format(writer=context.writer,
                                                   node=context.node
                                                   if context.node is not None
                                                   else "",
                                                   value=context.value)
        self._socket.write(line)        # master: "MNEMONIC VAL <CR><LF>"
        ack = self.socket.readline()    # remote: "ACK<CR><LF>"
        self._check_error(line, ack)

    @staticmethod
    def _check_error(line, ack):
        if ack.startswith(chr(ascii.NAK)):
            raise PfeifferHardwareError(
                "Command %s not acknowledged." % line.strip())
        elif not ack.startswith(chr(ascii.ACK)):
            raise PfeifferDriverError(
                "Command %s raised unknown error." % line.strip())


class Maxigauge(drv.Subsystem):

    """Maxigauge subsystem.

    .. graphviz:: gv/Maxigauge.txt

    """
    def __init__(self, socket):
        super().__init__()
        self.setProtocol(CommunicationProtocol(socket))
        # Controller subsystem
        self.errors = Cmd("ERR", access=Access.RO, rfunc=_parse_error)
        self.unit = Cmd("UNI", access=Access.RO, rfunc=lambda msg: 
                        {0: "mbar", 1: "Torr", 2: "Pascal"}[int(msg)])
        # Display subsystem
        # UNI
        # DCB
        # DCC
        # DCS
        # Switching subsystem
        # SPx
        # SPS
        # PUC
        # Parameters subsystem
        # LOC
        # FIL
        # CAx
        # OFC
        # FSR
        # DGS
        # SAV
        # Interfaces subsystem
        # RSX
        # BAU
        # NAD
        # Gauge subsystem
        self.gauge = drv.Subsystem(self)
        # SEN bool
        # SCx
        # PRx
        self.gauge.pressure = Cmd("PR", access=Access.RO, rfunc=_parse_pressure)
        # DCD
        # CID


class TestMaxigauge(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {"PR1\r\n": "\x06\r\n0,1.234E-2\r\n",
                      "UNI\r\n": "\x06\r\n0\r\n",
                      "\x05\r\n": ""}
        self.i = Maxigauge(socket)

    def test_read_sensor(self):
        self.assertEqual(self.i.gauge.pressure.read(node=1), 0.01234)

    def test_read_controller(self):
        self.assertEqual(self.i.unit.read(), "mbar")


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    unittest.main()
