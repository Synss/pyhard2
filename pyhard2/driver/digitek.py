"""
Driver for Digitek multimeters.

Notes
-----
Driver written with information from mikrocontroller.net [1]_ and Stefan
Heindel's matlab script.[2]_

References
----------
.. [1] `"DT80000 -> RS232<-???" <www.mikrocontroller.net/topic/68722>`_
.. [2] `<http://www.mikrocontroller.net/topic/68722#1574560>`_

"""

import pyhard2.driver as drv
Param = drv.Parameter


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
    name, unit, prefactor = Subsystem.units.get(mode, ('?', '?', 1.0))
    if value == "inf":
        return value
    else:
        return sign * value * prefactor * 10**scale


def parse_unit(prim):
    """Extract unit."""
    mode = (ord(prim[RANGE]) & 0b01111000) >> 3
    name, unit, prefactor = Subsystem.units.get(mode, ('?', '?', 1.0))
    return unit

def parse_errors(prim):
    """Extract error from primary message."""
    if ord(prim[ERR]) & 0x20 != 0:
        return "low battery"


class Subsystem(drv.Subsystem):

    """Main subsystem."""

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

    mode = Param(0x89, getter_func=lambda prim:
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

    measure = Param(0x89, getter_func=parse_measure)
    unit = Param(0x89, getter_func=parse_unit)
    errors = Param(0x89, getter_func=parse_errors)
    bargraph = Param(0x8A, getter_func=lambda prim:
                     ord(prim[6]) / 20.0 * 100.0)  # 0..20 = 0..100%


class DT80000(drv.Instrument):

    """Multimeter Digitek DT80000"""

    def __init__(self, socket, async=False):
        super(DT80000, self).__init__()

        socket.baudrate = 9600
        socket.timeout = 2.0
        socket.newline = "\r"

        protocol = drv.SerialProtocol(socket, async,
                                      fmt_read="{param[getcmd]:c}")

        self.main = Subsystem(protocol)

