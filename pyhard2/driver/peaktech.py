# vim: tw=120
"""Drivers for the Peaktech PT1885 power supply.

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


def _parser(selector):
    """Wrapper for parsers."""
    def parse_voltage(x):
        """Return voltage."""
        return int(x[0:3])

    def parse_current(x):
        """Return current."""
        return int(x[3:6])

    return dict(voltage=parse_voltage,
                current=parse_current)[selector]

def _scale(factor):
    """Wrapper for scaling."""
    def scaler(x):
        """Returned scaled `x` value."""
        return int(x * factor)
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
        self._socket.newline = "\r\n"

    def read(self, context):
        node = context.node if context.node is not None else 0
        self._socket.write("{reader}{node:02d}\r\n".format(reader=context.reader,
                                                           node=node))
        ans = self._socket.readline()
        assert(self._socket.readline() == "OK\r")
        return ans

    def write(self, context):
        node = context.node if context.node is not None else 0
        self._socket.write("{writer}{node:02d} {value}\r\n".format(writer=context.writer,
                                                                   node=node,
                                                                   value=context.value))


class Pt1885(drv.Subsystem):

    """Driver for Peaktech PT1885 power supplies."""

    def __init__(self, socket):
        super(Pt1885, self).__init__()
        self.setProtocol(CommunicationProtocol(socket))
        self.max_voltage = Cmd('GMAX', rfunc=_parser("voltage"), access=Access.RO)
        self.max_current = Cmd('GMAX', rfunc=_parser("current"), access=Access.RO)
        self.voltage_lim = Cmd('GOVP', 'SOVP', rfunc=int, wfunc=int)
        self.set_voltage = Cmd('GETS', 'VOLT', rfunc=_parser("voltage"), wfunc=_scale(10))
        self.set_current = Cmd('GETS', 'CURR', rfunc=_parser("current"), wfunc=_scale(100))
        self.voltage = Cmd('GETD', minimum=0.0, rfunc=_parser("voltage"), access=Access.RO)
        self.current = Cmd('GETD', minimum=0.0, rfunc=_parser("current"), access=Access.RO)
        self.disable_output = Cmd("SOUT", access=Access.WO)
        self.voltage.maximum = self.max_voltage.read()
        self.current.maximum = self.max_current.read()


class TestPt1885(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {"GETD00\r\n": "012003\rOK\r",
                      "GMAX00\r\n": "070035\rOK\r", }
        self.i = Pt1885(socket)

    def test_read(self):
        self.assertEqual(self.i.voltage.read(), 12)
        self.assertEqual(self.i.current.read(), 3)

    def test_UI_limit(self):
        self.assertEqual(self.i.voltage.maximum, self.i.max_voltage.read())
        self.assertEqual(self.i.current.maximum, self.i.max_current.read())

if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logger = logging.getLogger("pyhard2")
    logger.setLevel(logging.DEBUG)
    unittest.main()
