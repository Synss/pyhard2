"""Standard commands for programmable instruments (SCPI).

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access
import ieee488_2

# SCPI std. mandates IEEE488.2, excluding IEEE488.1


class ScpiError(drv.DriverError): pass


class ScpiCommunicationProtocol(drv.CommunicationProtocol):

    """SCPI protocol."""

    def __init__(self, socket, parent=None):
        super(ScpiCommunicationProtocol, self).__init__(socket, parent)

    @staticmethod
    def _scpiPath(context):
        return ":".join(subsystem.mnemonic
                        for subsystem in reversed(context.path)
                        if isinstance(subsystem, ScpiSubsystem))

    @staticmethod
    def _scpiStrip(path):
        return "".join((c for c in path if c.isupper() or not c.isalpha()))

    def read(self, context):
        msg = "{path}?\n".format(
            path=self._scpiStrip(":".join((self._scpiPath(context),
                                           context.reader))))
        self._socket.write(msg)
        return self._socket.readline()

    def write(self, context):
        if context.value is True:
            context.value = "ON"
        elif context.value is False:
            context.value = "OFF"
        msg = "{path} {value}\n".format(
            path=self._scpiStrip(":".join((self._scpiPath(context),
                                           context.writer))),
            value=context.value)
        self._socket.write(msg)


class ScpiSubsystem(drv.Subsystem):

    """`Subsystem` with a mnemonic."""

    def __init__(self, mnemonic, parent=None):
        super(ScpiSubsystem, self).__init__(parent)
        self.mnemonic = mnemonic


class ScpiRequired(ieee488_2.Ieee488_2Subsystem):

    """Required commands from the IEEE 488.2 standard."""

    def __init__(self, socket, parent=None):
        super(ScpiRequired, self).__init__(socket, parent)
        self._scpi = drv.Subsystem(self)
        self._scpi.setProtocol(ScpiCommunicationProtocol(socket, self))
        # SYSTem
        self.system = ScpiSubsystem("SYSTem", self._scpi)
        self.system.error = ScpiSubsystem("ERRor", self.system)
        self.system.error.next = Cmd("NEXT", access=Access.RO)
        self.system.version = Cmd("VERSion", rfunc=float, access=Access.RO)
        # STATus
        self.status = ScpiSubsystem("STATus", self._scpi)
        self.status.operation = ScpiSubsystem("OPERation", self.status)
        self.status.operation.event = Cmd("EVENt", access=Access.RO)
        self.status.operation.condition = Cmd("CONDition", access=Access.RO)
        self.status.operation.enable = Cmd("ENABle", access=Access.RW)
        self.status.questionable = ScpiSubsystem("QUEStionable", self.status)
        self.status.preset = Cmd("PRESet", access=Access.WO)


class ScpiDigitalMeter(ScpiRequired):

    """SCPI Instrument Classes - 3 Digital Meters

    Base functionality of a digital meter.

    """
    def __init__(self, socket, meter_fn, parent=None):
        super(ScpiDigitalMeter, self).__init__(socket, parent)
        if meter_fn not in ("VOLTage VOLTage:DC VOLTage:AC".split() +
                            "CURRent CURRent:DC CURRent:AC".split() +
                            "RESistance FRESistance".split()):
            raise ScpiError("Unknown digital meter")
        self.configure = ScpiSubsystem("CONFigure", self._scpi)
        # SCALar:meter_fn
        self.fetch = ScpiSubsystem("FETCh", self._scpi)
        # SCALar:meter_fn
        self.read = ScpiSubsystem("READ", self._scpi)
        # SCALar:meter_fn
        self.measure = ScpiSubsystem("MEASure", self._scpi)
        # SCALar:meter_fn
        # Base device-oriented functions
        self.sense = ScpiSubsystem("SENSe", self._scpi)
        self.sense.function = ScpiSubsystem("FUNCtion", self.sense)
        """
        SENSe:
          FUNCtion:
            ON: function
            %(meter_fun)s:
              RANGe:
                P_UPPer_range: # num
                P_AUTO_range:  # bool
              RESolution # num
        """
        self.initiate = ScpiSubsystem("INITitiate", self._scpi)
        self.initiate.immediate = ScpiSubsystem("IMMediate", self.initiate)
        self.initiate.immediate.all = Cmd("ALL", access=Access.WO)
        self.initiate.abort = Cmd("ABORt", access=Access.WO)
        self.trigger = ScpiSubsystem("TRIGger", self._scpi)
        self.trigger.sequence = ScpiSubsystem("SEQuence", self.trigger)
        self.trigger.sequence.count = Cmd("COUNt")  # num
        self.trigger.sequence.delay = Cmd("DELay")  # num
        self.trigger.sequence.source = Cmd("SOURce")  # str


class ScpiDCVoltmeter(ScpiDigitalMeter):

    """SCPI Voltmeter.

    .. graphviz:: gv/ScpiDCVoltmeter.txt

    """
    def __init__(self, socket, parent=None):
        super(ScpiDCVoltmeter, self).__init__(socket, "VOLTage", parent)
        # SENSe: see Command Ref 18.20


class ScpiACVoltmeter(ScpiDigitalMeter):
    
    def __init__(self, socket, parent=None):
        super(ScpiACVoltmeter, self).__init__(socket, "VOLTage:AC", parent)


class ScpiDCAmmeter(ScpiDigitalMeter):
    
    def __init__(self, socket, parent=None):
        super(ScpiDCAmmeter, self).__init__(socket, "CURRent", parent)


class ScpiACAmmeter(ScpiDigitalMeter):

    def __init__(self, socket, parent=None):
        super(ScpiACAmmeter, self).__init__(socket, "CURRent:AC", parent)


class ScpiOhmmeter(ScpiDigitalMeter):
    
    def __init_(self, socket, parent=None):
        super(ScpiOhmmeter, self).__init__(socket, "RESistance", parent)


class ScpiFourWireOhmmeter(ScpiDigitalMeter):

    def __init__(self, socket, parent=None):
        super(ScpiFourWireOhmmeter, self).__init__(socket, "FRESistance", parent)


class ScpiPowerSupply(ScpiRequired):

    """SCPI Instrument Classes - 7 Power Supplies.

    .. graphviz:: gv/ScpiPowerSupply.txt

    """
    def __init__(self, socket, parent=None):
        super(ScpiPowerSupply, self).__init__(socket, parent)
        self.output = ScpiSubsystem("OUTPUT", self._scpi)
        self.output.state = Cmd("STATe")
        self.source = ScpiSubsystem("SOURce", self._scpi)
        # bit 1 for current; bit 0 for voltage; bit 0+1 for both
        self.source.current = Cmd("CURRent", rfunc=float)
        self.source.voltage = Cmd("VOLTage", rfunc=float)
        self.status.questionable.current = Cmd("CURRent")
        self.status.questionable.voltage = Cmd("CURRent")
        self.measure = ScpiSubsystem("MEASure", self._scpi)
        self.measure.current = Cmd("CURRent", rfunc=float)
        self.measure.voltage = Cmd("VOLTage", rfunc=float)


class TestScpi(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {"SOUR:VOLT?\n": "1.7\n",
                      "SOUR:CURR?\n": "0.5\n",
                      "SYST:VERS?\n": "1.2345\n",
                      "*RST\n": "",
                     }
        self.i = ScpiPowerSupply(socket)

    def test_read_voltage(self):
        self.assertEqual(self.i.source.voltage.read(), 1.7)

    def test_read_current(self):
        self.assertEqual(self.i.source.current.read(), 0.5)

    def test_required_subsystem(self):
        self.assertEqual(self.i.system.version.read(), 1.2345)

    def test_4882(self):
        self.i.reset.write()


if __name__ == "__main__":
    unittest.main()

