# vim: tw=120
"""Driver for Digitek multimeters.

Note:
    Driver written with information from mikrocontroller.net [1]_ and
    Stefan Heindel's matlab script.[2]_

Reference:
    .. [1] `"DT80000 -> RS232<-???" <www.mikrocontroller.net/topic/68722>`_
    .. [2] `<http://www.mikrocontroller.net/topic/68722#1574560>`_

"""

import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


ECHO, RANGE, SCALE, SIGN, ERR = 0, 1, 2, 4, 4  # BYTES
VALBEG, VALEND = 5, 10  # BYTES


def parse_measure(prim):
    """Extract measure."""
    sign = -1.0 if ord(prim[SIGN]) & 0x10 != 0 else 1.0
    value = float(prim[VALBEG:VALEND]
                  if ord(prim[ERR]) & 0b1000 == 0
                  else 'inf')  # overload
    mode  = (ord(prim[RANGE]) & 0b01111000) >> 3
    scale = (ord(prim[SCALE]) & 0b00111000) >> 3
    name, unit, prefactor = DT80k.units.get(mode, ('?', '?', 1.0))
    if value == "inf":
        return value
    else:
        return sign * value * prefactor * 10**scale


def parse_unit(prim):
    """Extract unit."""
    mode = (ord(prim[RANGE]) & 0b01111000) >> 3
    name, unit, prefactor = DT80k.units.get(mode, ('?', '?', 1.0))
    return unit

def parse_errors(prim):
    """Extract error from primary message."""
    if ord(prim[ERR]) & 0x20 != 0:
        return "low battery"


class CommunicationProtocol(drv.CommunicationProtocol):

    """Read-only communication with the device."""

    def __init__(self, socket):
        super(CommunicationProtocol, self).__init__(socket)
        self._socket.baudrate = 9600
        self._socket.timeout = 2.0
        self._socket.newline = "\r"

    def read(self, context):
        self._socket.write("{0:c}".format(context.reader))
        return self._socket.readline()


class DT80k(drv.Subsystem):

    """Driver for the Digitek DT80000 multimeter."""

    units = {4: ('Out', 'Hz', 1.0e-5),
             5: ('A DC', 'A', 1e-4),
             6: ('mA', 'mA', 1e-3),
             8: ('Temp', 'degC', 1e-3),
             9: ('Cap', 'uF', 1e-1),
             10: ('Freq', 'Hz', 1e-3),
             11: ('Diode', 'V', 1e-4),
             12: ('Ohm', 'Ohm', 1e-2),
             13: ('mV', 'mV', 1e-3),
             14: ('V', 'V', 1e-4),
             15: ('V AC', 'V', 1e-4)}

    def __init__(self, socket):
        super(DT80k, self).__init__()
        self.setProtocol(CommunicationProtocol(socket))
        self.mode = Cmd(0x89, rfunc=lambda prim:
                        {"\xC0": "temperature",
                         "\xC1": "temperature high",
                         "\xA0": "PWM out",
                         "\xA8": "Ampere",
                         "\xA9": "Ampere AC",
                         "\xAA": "Ampere AC + DC",  # primary display DC
                         # secondary display AC
                         "\xB0": "mA",
                         "\xB1": "mA AC",
                         "\xB2": "mA AC + DC",
                         "\xC8": "Cap.",
                         "\xD0": "Duty",
                         "\xE0": "Ohm",
                         "\xD8": "Diode",
                         "\xE8": "mV",
                         "\xE9": "ACmV + Hz",
                         "\xF0": "V",
                         "\xF8": "V AC"}[prim[RANGE]])
        self.measure = Cmd(0x89, rfunc=parse_measure)
        self.unit = Cmd(0x89, rfunc=parse_unit)
        self.errors = Cmd(0x89, rfunc=parse_errors)
        self.bargraph = Cmd(0x8A, rfunc=lambda prim: ord(prim[6]) / 20.0 * 100.0)  # 0..20 = 0..100%


class TestDt80k(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {"\x89": "\x89\xA8\xC0\x81\x40\x30\x30\x30\x35\x33\x38\x0A"}
        self.i = DT80k(socket)

    def test_read_measure(self):
        self.assertEqual(self.i.measure.read(), 0.0053)

    def test_read_unit(self):
        self.assertEqual(self.i.unit.read(), "A")


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logger = logging.getLogger("pyhard2")
    logger.setLevel(logging.DEBUG)
    unittest.main()
