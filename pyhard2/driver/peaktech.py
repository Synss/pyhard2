"""
Peaktech drivers
================

Drivers for the Peaktech PT1885 power supply.


Communication uses an ASCII protocol:

.. uml::

    group Set
    User    ->  Instrument: {mnemonic}{node} {value}
    end
    group Query
    User    ->  Instrument: {mnemonic}{node}
    User    <-- Instrument: {values}
    end

"""

import pyhard2.driver as drv
Param = drv.Parameter
Action = drv.Action


def parser(selector):
    """Wrapper for parsers."""
    def parse_voltage(x):
        """Return voltage."""
        return int(x[0:3])

    def parse_current(x):
        """Return current."""
        return int(x[3:6])

    return dict(voltage=parse_voltage,
                current=parse_current)[selector]

def scale(factor):
    """Wrapper for scaling."""
    def scaler(x):
        """Returned scaled `x` value."""
        return int(x * factor)
    return scaler


class Subsystem(drv.Subsystem):
    """Main subsystem."""

    max_voltage = Param('GMAX', getter_func=parser("voltage"), read_only=True)
    max_current = Param('GMAX', getter_func=parser("current"), read_only=True)
    voltage_lim = Param('GOVP', 'SOVP', getter_func=int, setter_func=int)
    set_voltage = Param('GETS', 'VOLT',
                        getter_func=parser("voltage"), setter_func=scale(10))
    set_current = Param('GETS', 'CURR',
                        getter_func=parser("current"), setter_func=scale(100))
    voltage = Param('GETD', getter_func=parser("voltage"), read_only=True)
    current = Param('GETD', getter_func=parser("current"), read_only=True)

    disable_output = Action("SOUT")


class PT1885(drv.Instrument):
    """Driver for Peaktech PT1885 power supply."""

    def __init__(self, socket, async=False, node=0):
        super(PT1885, self).__init__()
        socket.timeout = 3.0
        socket.newline = "\r\n"
        protocol = drv.SerialProtocol(
            socket,
            async,
            fmt_read="{param[getcmd]}{protocol[node]:0.2i}\r\n",
            fmt_write="{param[setcmd]}{protocol[node:0.2i]} {val}\r\n",
        )
        protocol.node = node
        self.main = drv.Subsystem(protocol)


__all__ = ["PT1885"]
