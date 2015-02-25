"""Keithley driver.

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access
import pyhard2.driver.ieee.scpi as scpi


class Model6487(scpi.ScpiRequired):

    """Driver for Keithley Model 6487 Picoammeter/Voltage Source.

    .. graphviz:: gv/Model6487.txt

    """
    def __init__(self, socket, parent=None):
        super(Model6487, self).__init__(socket, parent)
        # CALCulate subsystem
        self.calculate = scpi.ScpiSubsystem("CALCulate", self._scpi)
        self.calculate.format = Cmd("FORMat")
        self.calculate.kmath = scpi.ScpiSubsystem("KMATh", self.calculate)
        self.calculate.kmath.mmfactor = Cmd("MMFactor", rfunc=float,
                                            minimum=-9.99999e20,
                                            maximum= 9.99999e20)
        self.calculate.kmath.ma1factor = self.calculate.kmath.mmfactor
        self.calculate.kmath.mbfactor = Cmd("MBFactor", rfunc=float,
                                            minimum=-9.99999e20,
                                            maximum= 9.99999e20)
        self.calculate.kmath.ma0factor = self.calculate.kmath.mbfactor
        self.calculate.kmath.units = Cmd("MUNits")
        self.calculate.state = Cmd("STATe")
        self.calculate.data = Cmd("DATA", access=Access.RO, rfunc=float)
        # DISPlay subsystem
        self.display = scpi.ScpiSubsystem("DISPlay", self._scpi)
        self.display.digits = Cmd("DIGits", minimum=4, maximum=7, rfunc=int)
        self.display.enable = Cmd("ENABle")
        self.display.window = scpi.ScpiSubsystem("WINDow", self.display)
        self.display.window.text = scpi.ScpiSubsystem("TEXT", self.display.window)
        self.display.window.data = Cmd("DATA")
        self.display.window.state = Cmd("STATe")


class Model6487Test(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {"CALC:STAT ON\n": "",
                      "CALC:KMAT:MMF 0.002\n": "",
                      "CALC:DATA?\n": "12",}
        self.i = Model6487(socket)


    def test_read(self):
        self.assertEqual(self.i.calculate.data.read(), 12)

    def test_write(self):
        self.i.calculate.kmath.mmfactor.write(2e-3)

    def test_write_bool(self):
        self.i.calculate.state.write(True)


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    unittest.main()
