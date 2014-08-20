"""Arun Microelectronics Ltd. gauge drivers

Driver for Arun Microelectronics Ltd. (AML) gauges according to the
manual of an NGC2D instrument, the driver should also support PGC1
instruments.

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


def _parse_stat_byte(stat):
    """Parse status byte."""
    mode = 'local' if stat & 0b10000 == 0 else 'remote'
    ig = 1 if stat & 0b1000000 == 0 else 2
    connected = stat & 0b10000000 == 0
    return (mode, ig, connected)

def _parse_err_byte(err):
    """Parse error byte."""
    error = err & 0b1 == 0
    temperature_error = err & 0b10 == 0
    temperature_warning = err & 0b1000 == 0
    return (error, temperature_error, temperature_warning)

def _parser(type_):
    """Wrap message parsers.

    Parameters:
        type_ (str): {"measure", "unit", "type", "status", "error"}

    """
    def parser(status):
        """Parse message."""
        ig_type = {"I": "ion gauge",
                   "P": "Pirani",
                   "M": "capacitance manometer"}.get(status[1], "error")
        stat, err = status[4:6]
        stat = _parse_stat_byte(ord(stat))
        err = _parse_err_byte(ord(err))
        pressure = float(status[5:12])
        unit = {"T": "Torr",
                "P": "Pascal",
                "M": "mBar"}.get(status[13], "error")
        return dict(measure=pressure,
                    unit=unit,
                    type=ig_type,
                    status=stat,
                    error=err,
                   )[type_]
    return parser


class Protocol(drv.CommunicationProtocol):

    """Communication protocol.

    Communication is read only:

    .. uml::

        group Query
        User    ->  Instrument: "*{command}{node}"
        note right: {node} is not used on NGC2D instruments
        User    <-- Instrument: 17-bytes response
        end

    """
    def __init__(self, socket):
        super(Protocol, self).__init__(socket)
        self._socket.baudrate = 9600
        self._socket.timeout = 0.1
        self._socket.newline = "\r\n"
        self._node = 0  # required for compatibility with older hardware

    def read(self, context):
        self._socket.write("*{reader}{node}\r\n".format(
            reader=context.reader, node=self._node))
        return self._socket.readline()


class Ngc2d(drv.Subsystem):

    """Driver for NGC2D ion gauges.

    .. graphviz:: gv/Ngc2d.txt

    """
    def __init__(self, socket):
        super(Ngc2d, self).__init__()
        self.setProtocol(Protocol(socket))
        # Commands
        self.poll = Cmd("P", Access.WO)
        # control
        # release
        self.reset_error = Cmd("E", Access.WO)
        self.measure = Cmd("S", rfunc=_parser("measure"))
        self.unit = Cmd("S", rfunc=_parser("unit"))
        self.IG_type = Cmd("S", rfunc=_parser("type"))
        self.error = Cmd("S", rfunc=_parser("error"))
        self.status = Cmd("S", rfunc=_parser("status"))
        # emission
        # gauge off
        # override
        # inhibit


class TestAml(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        # Return a pressure of 1.3e-7 mbar.
        socket.msg = {"*S0\r\n": "GI1\x65\x001.3E-07,M0\r\n"}
        self.i = Ngc2d(socket)

    def test_measure(self):
        self.assertEqual(self.i.measure.read(), 1.3e-7)

    def test_unit(self):
        self.assertEqual(self.i.unit.read(), "mBar")


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logger = logging.getLogger("pyhard2")
    logger.setLevel(logging.DEBUG)
    unittest.main()
