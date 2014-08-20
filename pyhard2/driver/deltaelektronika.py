# vim: tw=120
"""Delta-Electronica drivers

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


class CommunicationProtocol(drv.CommunicationProtocol):

    """Communication using the Delta Programming Language (DPL)

    Warning:
        the Delta Programming Language (DPL) has been obsoleted by
        Delta-Electronica.

    """
    def __init__(self, socket):
        super(CommunicationProtocol, self).__init__(socket)
        self._socket.timeout = 5.0
        self._socket.newline = "\n"

    def read(self, context):
        self._socket.write("{0}\n".format(context.reader))
        return self._socket.readline()

    def write(self, context):
        self._socket.write("{0} {1}\n".format(context.writer, context.value))


def _parse_error(err):
    """Return string from error code."""
    return {0: "No error",
            1: "Syntax error",
            2: "Channel-number error",
            3: "Float format error",
            5: "Max voltage range",
            6: "Max current range",
            9: "Slave address error (eeprom)",
            10: "Slave word error (eeprom)",
            11: "Slave data error (eeprom)",
            13: "Checksum error",
            14: "Over range error",
            15: "Illegal password",
            16: "RCL error",
            17: "Invalid character",
            18: "Not connected with PSU",
            19: "Command not supported, wrong configuration"}[int(err)]


class DplInstrument(drv.Subsystem):

    """Driver using the DPL language.

    .. graphviz:: gv/DplInstrument.txt

    """
    def __init__(self, socket):
        super(DplInstrument, self).__init__()
        self.setProtocol(CommunicationProtocol(socket))
        self.step_mode_voltage = Cmd("SA", rfunc=float, doc="Step mode A channel (voltage)")
        self.step_mode_current = Cmd("SB", rfunc=float, doc="Step mode B channel (current)")
        self.max_voltage = Cmd("FU", rfunc=float, doc="Input maximum voltage")
        self.max_current = Cmd("FI", rfunc=float, doc="Input maximum current")
        self.voltage = Cmd("U", "MA?", minimum=0.0, rfunc=float, doc="Output voltage")
        self.current = Cmd("I", "MB?", minimum=0.0, rfunc=float, doc="Output current")
        self.error = Cmd("ERR?", rfunc=_parse_error, access=Access.RO, doc="Report last error")
        self.identification = Cmd("ID?", access=Access.RO, doc="Report identity of the PSC")
        #self.scpi = Cmd("SCPI", access=Access.WO, doc="Switch to the SCPI parser")
        try:
            self.voltage.maximum = self.max_voltage.read()
            self.current.maximum = self.max_current.read()
        except KeyError:  # Ignore exception raised during auto documentation.
            pass


class TestDpl(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {"U\n": "13\r\n",
                    "FU\n": "70\r\n",
                    "FI\n": "35\r\n", }
        self.i = DplInstrument(socket)

    def test_read(self):
        self.assertEqual(self.i.voltage.read(), 13)

    def test_UI_limit(self):
        self.assertEqual(self.i.voltage.maximum, self.i.max_voltage.read())
        self.assertEqual(self.i.current.maximum, self.i.max_current.read())


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logger = logging.getLogger("pyhard2")
    logger.setLevel(logging.DEBUG)
    unittest.main()
