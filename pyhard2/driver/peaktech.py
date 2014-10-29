"""Drivers for the Peaktech PT1885 power supply.

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


def _parser(selector, size=3):
    """Wrapper for parsers."""
    def parse_voltage(x):
        """Return voltage."""
        return float(x[0:size]) * 10.0**(2-size)

    def parse_current(x):
        """Return current."""
        return float(x[size:2*size]) * 10.0**(1-size)

    return dict(voltage=parse_voltage,
                current=parse_current)[selector]

def _scale(factor):
    """Wrapper for scaling."""
    def scaler(x):
        """Returned scaled `x` value."""
        return int(round(x * factor))
    return scaler


class CommunicationProtocol(drv.CommunicationProtocol):

    """Communication uses an ASCII protocol:

    .. uml::

        group Set
        User    ->  Instrument: {mnemonic}{node} {value}
        end
        group Query
        User    ->  Instrument: {mnemonic}{node}
        User    <-- Instrument: {values}
        end

    """
    def __init__(self, socket):
        super(CommunicationProtocol, self).__init__(socket)
        self._socket.timeout = 3.0
        self._socket.newline = "\r"

    def read(self, context):
        node = context.node if context.node is not None else 0
        self._socket.write("{reader}{node:02d}\r".format(reader=context.reader,
                                                         node=node))
        ans = self._socket.readline()
        assert(self._socket.readline() == "OK\r")
        return ans

    def write(self, context):
        node = context.node if context.node is not None else 0
        self._socket.write("{writer}{node:02d}{value:03d}\r".format(
            writer=context.writer, node=node, value=context.value))
        assert(self._socket.readline() == "OK\r")


class Pt1885(drv.Subsystem):

    """Driver for Peaktech PT1885 power supplies.

    .. graphviz:: gv/Pt1885.txt

    """
    def __init__(self, socket):
        super(Pt1885, self).__init__()
        self.setProtocol(CommunicationProtocol(socket))
        self.max_voltage = Cmd('GMAX', rfunc=_parser("voltage"), access=Access.RO)
        self.max_current = Cmd('GMAX', rfunc=_parser("current"), access=Access.RO)
        self.voltage_lim = Cmd('GOVP', 'SOVP', rfunc=_parser("voltage"), wfunc=_scale(10))
        self.voltage = Cmd('GETS', 'VOLT', minimum=0.0, rfunc=_parser("voltage"), wfunc=_scale(10))
        self.current = Cmd('GETS', 'CURR', minimum=0.0, rfunc=_parser("current"), wfunc=_scale(100))
        self.voltage_meas = Cmd('GETD', rfunc=_parser("voltage", 4), access=Access.RO)
        self.current_meas = Cmd('GETD', rfunc=_parser("current", 4), access=Access.RO)
        #self.disable_output = Cmd("SOUT", access=Access.WO)
        try:
            self.voltage.maximum = self.max_voltage.read()
            self.current.maximum = self.max_current.read()
        except KeyError:  # Ignore exception raised during auto documentation
            pass


class TestPt1885(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {"GETD00\r": "012003\rOK\r",
                      "GETS00\r": "012003\rOK\r",
                      "GMAX00\r": "400500\rOK\r",
                      "VOLT00014\r": "OK\r",
                     }
        self.i = Pt1885(socket)

    def test_read(self):
        self.assertAlmostEqual(self.i.voltage.read(), 1.2, 3)
        self.assertAlmostEqual(self.i.current.read(), 0.03, 3)

    def test_write(self):
        self.i.voltage.write(1.4)

    def test_UI_limit(self):
        self.assertEqual(self.i.voltage.maximum, self.i.max_voltage.read())
        self.assertEqual(self.i.current.maximum, self.i.max_current.read())


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logger = logging.getLogger("pyhard2")
    logger.setLevel(logging.DEBUG)
    unittest.main()
