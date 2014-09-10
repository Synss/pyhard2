"""Delta-Electronica drivers

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access
import pyhard2.driver.ieee.scpi as scpi


def _str2bool(s):
    return bool(int(s))

def _stripEot(msg):
    assert(msg.endswith("\x04"))
    return msg[:-1]


class DplProtocol(drv.CommunicationProtocol):

    """Communication using the Delta Programming Language (DPL)

    Warning:
        the Delta Programming Language (DPL) has been obsoleted by
        Delta-Electronica.

    """
    def __init__(self, socket):
        super(DplProtocol, self).__init__(socket)

    @staticmethod
    def _check_error(msg):
        if msg.startswith("ER"):
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
                    19: "Command not supported, wrong configuration"
                   }[int(msg[2:])]

    def read(self, context):
        self._socket.write("{0}\n".format(context.reader))
        return _stripEot(self._socket.readline())

    def write(self, context):
        self._socket.write("{0} {1}\n".format(context.writer, context.value))


class ScpiCommunicationProtocol(scpi.ScpiCommunicationProtocol):

    def read(self, context):
        return _stripEot(super(ScpiCommunicationProtocol, self).read(context))


class Sm700Series(drv.Subsystem):

    """Driver for Delta Elektronika SM700-Series power supplies.

    A Subset of the PSC488 EXT commands is implemented in the `dpl`
    subsystem as well as the SCPI-like commands found in the PSC 232 PSC
    488 Programming Manual (an html document).

    .. graphviz:: gv/Sm700Series.txt

    """
    def __init__(self, socket):
        super(Sm700Series, self).__init__()
        socket.timeout = 1.0
        # Termination character Controller -> PSC232: LF or CR
        # Termination character PSC232 -> Controller: EOT (\x04)
        socket.newline = "\x04"
        # DPL
        self.dpl = drv.Subsystem(self)
        self.dpl.setProtocol(DplProtocol(socket))
        self.dpl.step_mode_voltage = Cmd("SA", rfunc=float, doc="Step mode A channel (voltage)")
        self.dpl.step_mode_current = Cmd("SB", rfunc=float, doc="Step mode B channel (current)")
        self.dpl.max_voltage = Cmd("FU", rfunc=float, doc="Input maximum voltage")
        self.dpl.max_current = Cmd("FI", rfunc=float, doc="Input maximum current")
        self.dpl.voltage = Cmd("U", "MA?", minimum=0.0, rfunc=float, doc="Output voltage")
        self.dpl.current = Cmd("I", "MB?", minimum=0.0, rfunc=float, doc="Output current")
        self.dpl.error = Cmd("ERR?", access=Access.RO, doc="Report last error")
        self.dpl.identification = Cmd("ID?", access=Access.RO, doc="Report identity of the PSC")
        self.dpl.scpi = Cmd("SCPI", access=Access.WO, doc="Switch to the SCPI parser")
        self.dpl.dpl = Cmd("DPL", access=Access.WO, doc="Switch to the DPL parser")
        # SCPI
        self.setProtocol(ScpiCommunicationProtocol(socket))
        self.channel = Cmd("CH", rfunc=int)
        self.source = scpi.ScpiSubsystem("SOurce", self)
        self.source.voltage = Cmd("VOltage", rfunc=float, minimum=0.0)
        self.source.current = Cmd("CUrrent", rfunc=float, minimum=0.0)
        self.source.max_voltage = Cmd("VOltage:MAx", rfunc=float)
        self.source.max_current = Cmd("CUrrent:MAx", rfunc=float)
        self.source.function = scpi.ScpiSubsystem("FUnction", self.source)
        self.source.function.enable_remote_shutdown = Cmd("RSD", rfunc=_str2bool)
        self.source.function.output_a = Cmd("OUtA", rfunc=_str2bool)
        self.source.function.output_b = Cmd("OUtB", rfunc=_str2bool)
        self.source.function.output = Cmd("OUTPut", rfunc=_str2bool)
        self.source.function.lock_frontpanel = Cmd("FRontpanel:Lock", rfunc=_str2bool)
        self.measure = scpi.ScpiSubsystem("MEasure", self)
        self.measure.voltage = Cmd("VOltage", access=Access.RO)
        self.measure.current = Cmd("CUrrent", access=Access.RO)
        self.sense = scpi.ScpiSubsystem("SEnse", self)
        self.sense.digital = scpi.ScpiSubsystem("DIgital", self.sense)
        self.sense.digital.data = Cmd("DAta", access=Access.RO)
        self.sense.digital.extended_data = Cmd("EXtendeddata", access=Access.RO)
        self.sense.digital.switch = Cmd("SWitch", access=Access.RO)
        self.remote = scpi.ScpiSubsystem("REMote", self)
        self.remote.cv = Cmd("CV", rfunc=_str2bool)
        self.remote.cc = Cmd("CC", rfunc=_str2bool)
        self.local = scpi.ScpiSubsystem("LOCal", self)
        self.local.cv = Cmd("CV", rfunc=_str2bool, access=Access.WO)
        self.local.cc = Cmd("CC", rfunc=_str2bool, access=Access.WO)
        self.calibration = scpi.ScpiSubsystem("CAlibration", self)
        self.calibration.voltage = scpi.ScpiSubsystem("VOltage", self.calibration)
        self.calibration.current = scpi.ScpiSubsystem("CUrrent", self.calibration)
        self.calibration.voltage.measure = scpi.ScpiSubsystem("MEasure", self.calibration.voltage)
        self.calibration.current.measure = scpi.ScpiSubsystem("MEasure", self.calibration.current)
        for subsystem in (self.calibration.voltage, self.calibration.voltage.measure,
                          self.calibration.current, self.calibration.current.measure):
            subsystem.gain = Cmd("GAin", rfunc=int, minimum=1, maximum=16383)
            subsystem.offset = Cmd("OFfset", rfunc=int, minimum=0, maximum=254)
        # PAssword
        # PAssword:Reset
        self.custom_string = Cmd("*IDN?", "CU")
        # SP
        self.variables = Cmd("VAR", access=Access.RO)
        self.help = Cmd("HELP", access=Access.RO)
        # set max current and voltage:
        try:
            self.source.voltage.maximum = self.source.max_voltage.read()
            self.source.current.maximum = self.source.max_current.read()
        except KeyError:  # Ignore exception raised during auto documentation
            pass


class TestSm700(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {# DPL
                      "U\n": "13\r\n\x04",
                      "FU\n": "70\r\n\x04",
                      "FI\n": "35\r\n\x04",
                      # SCPI
                      "SO:VO?\n": "0.25\r\n\x04",
                      "SO:VO 0.25\n": "",
                      "SO:FU:RSD?\n": "0\r\n\x04",
                      "SO:FU:RSD OFF\n": "",
                      "CA:CU:ME:GA?\n": "14810\r\n\x04",
                      "SO:VO:MA?\n": "70\r\n\x04",
                      "SO:CU:MA?\n": "37\r\n\x04"
                     }
        self.i = Sm700Series(socket)

    def test_dpl_read(self):
        self.assertEqual(self.i.dpl.voltage.read(), 13)

    def test_scpi_read(self):
        self.assertEqual(self.i.source.voltage.read(), 0.25)

    def test_scpi_write(self):
        self.i.source.voltage.write(0.25)

    def test_scpi_read_fursd_bool(self):
        self.assertFalse(self.i.source.function.enable_remote_shutdown.read())

    def test_scpi_write_fursd_bool(self):
        self.i.source.function.enable_remote_shutdown.write(False)

    def test_scpi_read_cacumega(self):
        self.assertEqual(self.i.calibration.current.measure.gain.read(), 14810)

    def test_scpi_UI_limit(self):
        self.assertEqual(self.i.source.voltage.maximum, self.i.source.max_voltage.read())
        self.assertEqual(self.i.source.current.maximum, self.i.source.max_current.read())


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logger = logging.getLogger("pyhard2")
    logger.setLevel(logging.DEBUG)
    unittest.main()
