# vim: tw=120
"""Fluke drivers

Driver following the technical note entitled: "Fluke 189/187/98-IV/87-IV
Remote Interface Specification"

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


def _parse_measure(x):
    """Return measure."""
    return float(x.split(",")[1].split()[0])

def _parse_unit(x):
    """Return unit."""
    return ' '.join(x.split(",")[1].split()[1:])


class CommunicationProtocol(drv.CommunicationProtocol):

    """Protocol for Fluke model 189, 187, 89-IV, and 87-IV digital
    multimeters.

    Commands consist of two-letter codes that are sent from the computer
    to the meter.

    .. uml::

        group Default Setup
        User    ->  Meter: DS
        User    <-- Meter: ACK
        note right: ACK == {0, 1}, 0 for no error
        end

        group IDentification
        User    ->  Meter: ID
        User    <-- Meter: ACK
        User    <-- Meter: {id}
        end

        group Query Measurement
        User    ->  Meter: QM
        User    <-- Meter: ACK
        User    <-- Meter: QM,{reading}
        end

        group Reset Instrument
        User    ->  Meter: RI
        User    <-- Meter: ACK
        end

        group Set Function (key presses)
        User    ->  Meter: SF {key code}
        User    <-- Meter: ACK
        end

    """
    def __init__(self, socket):
        super(CommunicationProtocol, self).__init__(socket)
        self._socket.timeout = 1.0
        self._socket.newline = "\r"

    def read(self, context):
        self._socket.write("{reader}\r".format(reader=context.reader))
        assert(self._socket.readline() == "0\r")
        return self._socket.readline().strip()

    def write(self, context):
        self._socket.write("{writer}\r".format(writer=context.writer))
        assert(self._socket.readline() == "0\r")


class Fluke18x(drv.Subsystem):

    """Driver for the Fluke Series 18x multimeters.

    .. graphviz:: gv/Fluke18x.txt

    """
    def __init__(self, socket):
        super(Fluke18x, self).__init__()
        self.setProtocol(CommunicationProtocol(socket))
        self.button = drv.Subsystem(self)
        for name, code in dict(blue=10,
                               hold=11,
                               min_max=12,
                               rel=13,
                               up_arrow=14,
                               shift=15,
                               Hz=16,
                               range=17,
                               down_arrow=18,
                               backlight=19,
                               calibration=20,
                               auto_hold=21,
                               fast_min_max=22,
                               logging=23,
                               cancel=27,
                               wake_up=28,
                               setup=29,
                               save=30).iteritems():
            self.button.__setattr__("press_%s" % name, Cmd("SF %i" % code, access=Access.WO))
        self.identification = Cmd("ID", doc="""Return model, S/N and software version information""")
        self.measure = Cmd("QM", rfunc=_parse_measure, access=Access.RO)
        self.unit = Cmd("QM", rfunc=_parse_unit, access=Access.RO)
        self.default_setup = Cmd("DS", access=Access.WO)
        self.reset = Cmd("RI", access=Access.WO)


class TestFluke18x(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {"DS\r": "0\r",
                      "ID\r": "0\rFLUKE 89,V0.39,123456789\r",
                      "QM\r": "0\rQM,+47.66 KOhms\r",
                      "SF 10\r": "0\r"}
        self.i = Fluke18x(socket)

    def test_write(self):
        self.i.default_setup.write()

    def test_button_press(self):
        self.i.button.press_blue.write()

    def test_read_measure(self):
        self.assertEqual(self.i.measure.read(), 47.66)

    def test_read_id_string(self):
        self.assertEqual(self.i.identification.read(), "FLUKE 89,V0.39,123456789")


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logger = logging.getLogger("pyhard2")
    logger.setLevel(logging.DEBUG)
    unittest.main()
