"""
Delta-Electronica drivers
=========================

"""

import yaml
import pyhard2.driver as drv
import pyhard2.driver.ieee.scpi as scpi


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


class DplProtocol(drv.SerialProtocol):

    """Delta Programming Language protocol.

    .. warning::

        DPL has been obsoleted by Delta-Electronica.

    """

    def __init__(self, socket, async): 
        super(DplProtocol, self).__init__(
            socket,
            async,
            fmt_read="{param[getcmd]}\n",
            fmt_write="{param[setcmd]} {val}\n",
        )


class DplSubsystem(drv.Subsystem):

    """DPL subsystem."""

    step_mode_voltage = drv.Parameter("SA",
                                      doc="Step mode A channel (voltage)")
    step_mode_current = drv.Parameter("SB",
                                      doc="Step mode B channel (current)")
    max_voltage = drv.Parameter("FU", doc="Input maximum voltage")
    max_current = drv.Parameter("FI", doc="Input maximum current")
    voltage = drv.Parameter("U", "MA?", doc="Output voltage")
    current = drv.Parameter("I", "MB?", doc="Output current")
    error = drv.Parameter("ERR?", getter_func=_parse_error, read_only=True,
                          doc="Report last error")
    identification = drv.Parameter("ID?", read_only=True,
                                   doc="Report identity of the PSC")
    scpi = drv.Action("SCPI", doc="Switch to the SCPI parser")


class DplInstrument(drv.Instrument):

    """DPL instrument."""

    def __init__(self, socket, async=False):
        super(DplInstrument, self).__init__()

        socket.timeout = 5.0
        socket.newline = "\n"

        protocol = DplProtocol(socket, async)

        self.main = DplSubsystem(protocol)


class Psc232ext(scpi.ScpiInstrument):

    """SCPI instrument."""

    def __init__(self, socket, async=False):
        super(Psc232ext, self).__init__()

        socket.baudrate = 19200
        socket.timeout = 3

        self.add_subsystems_from_tree(yaml.load(
            """
            CAlculate:
                VOltage:
                    &gainoffset
                    P_GAin:
                    P_OFfset:
                    MEasure:
                        P_GAin:
                        P_OFset:
                CUrrent:
                    *gainoffset
            SOurce:
                VOltage:
                    P_MAx:
                CUrrent:
                    P_MAx:
                P_VOltage:
                P_CUrrent:
                #FU:
                #    A_RSD:
            MEasure:
                P_VOltage:
                P_CUrrent:
            MAIN:
                P_CHannel:
                A_HE:
                A_PA:
                A_TY:
                A_CU:
            """))


def _test():
    dpl = DplInstrument(drv.Serial())
    print(dpl)
    print("\n\n")
    instr = Psc232ext(drv.Serial())
    print(instr)
    print(instr.calculate.voltage.measure)


if __name__ == "__main__":
    _test()
