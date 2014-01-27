"""
Fluke drivers
=============

Driver following the technical note entitled: "Fluke 189/187/98-IV/87-IV
Remote Interface Specification"

"""

import pyhard2.driver as drv
Parameter = drv.Parameter
Action = drv.Action


def parse_measure(x):
    """Return measure."""
    return float(x.split(",")[1].split()[0])

def parse_unit(x):
    """Return unit."""
    return ' '.join(x.split(",")[1].split()[1:])


class Protocol(drv.SerialProtocol):

    """
    Protocol for Fluke model 189, 187, 89-IV, and 87-IV digital
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


    def __init__(self, socket, async):
        super(Protocol, self).__init__(socket, async,
                                       fmt_read="{param[getcmd]}\r")

    def _encode_read(self, subsys, param):
        ack = super(Protocol, self)._encode_read(subsys, param)
        assert(ack == "0")
        return self.socket.readline().strip()


class Subsystem(drv.Subsystem):

    """Main subsystem."""

    def __init__(self, protocol):
        super(Subsystem, self).__init__(protocol)
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
            self.add_action_by_name("press_button_%s" % name, "SF %i" % code)

    identification = Parameter("ID", doc="""Return model, S/N and software
                                         version information""")
    measure = Parameter("QM", getter_func=parse_measure, read_only=True)
    unit = Parameter("QM", getter_func=parse_unit, read_only=True)
    default_setup = Action("DS")
    reset = Action("RI")


class Fl18x(drv.Instrument):

    """Fluke Series 18x instrument driver."""

    def __init__(self, socket, async=False):
        super(Fl18x, self).__init__()
        socket.timeout = 1.0
        socket.newline = "\r"
        protocol = Protocol(socket, async)
        self.main = Subsystem(protocol)


def main(argv):
    """Unit tests."""
    com = drv.Serial("COM4" if len(argv) < 2 else argv[1])
    mm = Fl18x(com)
    print(mm.measure)
    mm.press_button_blue()
    print(mm.measure)
    mm.press_button_blue()


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))

