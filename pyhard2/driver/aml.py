"""
Arun Microelectronics Ltd. gauge drivers
========================================

Driver for Arun Microelectronics Ltd. (AML) gauges according to the
manual of an NGC2D instrument, the driver should also support PGC1
instruments.


Communication is read only:

.. uml::

    group Query
    User    ->  Instrument: *{command}{node}
    note right: {node} is not used on NGC2D instruments
    User    <-- Instrument: 17-bytes response
    end

"""

import pyhard2.driver as drv
Action = drv.Action
Parameter = drv.Parameter

__all__ = ["NGC2D"]


class TestSocket(drv.TestSocketBase):

    def __init__(self):
        # Return a pressure of 1.3e-7 mbar.
        super(TestSocket, self).__init__(
            msg={"*S0\r\n": "GI1\x65\x001.3E-07,M0\r\n"},
            newline="\r\n")


def _parse_stat_byte(stat):
    """Parse status byte."""
    mode = 'local' if stat & 0b10000 == 0 else 'remote'
    ig = 1 if stat & 0b1000000 == 0 else 2
    connected = stat & 0b10000000 == 0
    return (mode, ig, connected)

def _parse_err_byte(err):
    """Parse error byte."""
    error = err & 0b1 == 0
    temperature_error = err & 0b10 == 0
    temperature_warning = err & 0b1000 == 0
    return (error, temperature_error, temperature_warning)

def _parser(type_):
    """Wrap message parsers.

    Parameters
    ----------
    type_ : {"measure", "unit", "type", "status", "error"}
    """
    def parser(status):
        """Parse message."""
        ig_type = {"I": "ion gauge",
                   "P": "Pirani",
                   "M": "capacitance manometer"}.get(status[1], "error")
        stat, err = status[4:6]
        stat = _parse_stat_byte(ord(stat))
        err = _parse_err_byte(ord(err))
        pressure = float(status[5:12])
        unit = {"T": "Torr",
                "P": "Pascal",
                "M": "mBar"}.get(status[13], "error")
        return dict(measure=pressure,
                    unit=unit,
                    type=ig_type,
                    status=stat,
                    error=err,
                   )[type_]
    return parser


class Subsystem(drv.Subsystem):

    """Main subsystem."""

    poll = Action("P")

    # control
    # release

    reset_error = Action("E")

    measure = Parameter("S", getter_func=_parser("measure"))
    unit = Parameter("S", getter_func=_parser("unit"))
    IG_type = Parameter("S", getter_func=_parser("type"))
    error = Parameter("S", getter_func=_parser("error"))
    status = Parameter("S", getter_func=_parser("status"))

    # emission

    #def select_IG(self, gauge_ID):
    #    gauge_ID = in_bounds(gauge_ID, 1, 2)
    #    self.socket.set("i0%i" % gauge_ID)

    # gauge off
    # override
    # inhibit


class NGC2D(drv.Instrument):

    """Instrument for AML NGC2D and PGC1 gauge controllers."""

    def __init__(self, socket, async=False, node=0):
        super(NGC2D, self).__init__()

        socket.baudrate = 9600
        socket.timeout = 0.1
        socket.newline = "\r\n"

        protocol = drv.SerialProtocol(
            socket,
            fmt_read="*{param[getcmd]}{protocol[node]}\r\n",
            )
        protocol.node = node

        self.main = Subsystem(protocol)


def main():
    """Unit tests.""" 
    s = TestSocket()
    i = NGC2D(s)
    assert i.measure == 1.3e-7
    assert i.unit == "mBar"


if __name__ == "__main__":
    main()

