"""
SCPI drivers
============

Standard commands for programmable instruments.


Commands may be added using the method
:meth:`ScpiInstrument.add_subsystems_from_tree`.

The syntax follows the SCPI standard as closely as possible as can be seen in
the following example::

    instr = ScpiInstrument(Serial())
    instr.add_subsystems_from_tree(yaml.load(\"\"\"
        SYSTem:
            P_ERRor:
            P_VERSion:
        STATus:
            OPERation:
                &op
                P_CONDition:
                P_ENABle: {read_only: true}
                P_EVENt:
            A_PRESet:
            QUESTionable:
                *op
    \"\"\"))

creates an instrument with the subsystems `system`, `status`,
`status.operation` and `status.questionable`.  The SCPI mnemonics are the
capitalized part of the name and the `subsystem` is named with the whole
word(s), in lower case.  The commands are prefixed with ``P_`` or ``A_`` adding
a `parameter` or an `action` to the subsystem, respectively.  Subsystems can be
nested and extra arguments required at the construction of the command are
given in a dictionary (`status.operation.enable` is read-only, here).

"""
import yaml

import pyhard2.driver as drv

# SCPI std. mandates IEEE488.2, excluding IEEE488.1
from ieee488_2 import Mandatory as Ieee488_2
from ieee488_2 import IeeeProtocol


def _bool(setter):
    def setter(b):
        return "ON" if b else "OFF"
    def getter(b):
        return b == "ON"
    return dict(setter=setter,
                getter=getter)


def _strip_lower(string):
    """Only return upper case from `string`."""
    return "".join((char for char in string if char.isupper()))


def _paths(tree, current=()):
    """Traverse tree and yield path to leaves with corresponding list
       of leaves."""
    for node, subtree in tree.iteritems():
        if node[:2] in ("A_", "P_"):
            yield current, {node: subtree}
        else:
            for path in _paths(subtree, current + (node,)):
                yield path


class ScpiProtocol(drv.SerialProtocol):

    """SCPI protocol."""

    def __init__(self):
        super(ScpiProtocol, self).__init__(
            fmt_read="{subsys[mnemonic]}:{param[getcmd]}?\r",
            fmt_write="{subsys[mnemonic]}:{param[setcmd]} {val}\r",
        )


class ScpiSubsystem(drv.Subsystem):

    """
    `Subsystem` with a mnemonic.
    
    Parameters
    ----------
    instrument
    mnemonic : str

    """
    def __init__(self, instrument, mnemonic):
        super(ScpiSubsystem, self).__init__(instrument)
        self.mnemonic = mnemonic


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class ScpiInstrument(drv.Instrument):

    """Construct SCPI subsystems from YAML formula."""

    def __init__(self, socket, protocol=None):
        super(ScpiInstrument, self).__init__(socket, ScpiProtocol()
                                             if protocol is None else
                                             protocol)

    def add_subsystems_from_tree(self, tree):
        """Create subsystems and commands from a YAML formula mimicking
           the SCPI standard."""

        def get_subsystem(path, parent=self):
            """Return `subsystem` at `path`."""
            mnemo, path = path[0], path[1:]
            try:
                subsys = getattr(parent, mnemo.lower())
            except AttributeError:
                subsys = type(mnemo.lower(), (ScpiSubsystem,), {})(self, "")
                setattr(parent, mnemo.lower(), subsys)
            return get_subsystem(path, subsys) if path else subsys

        for path, nodes in _paths(tree):
            subsys = get_subsystem(path)
            node, kwargs = nodes.iteritems().next()
            typ, sep, name = node.partition("_")
            getcmd = ":".join(_strip_lower(mnemo) for mnemo in path + (name,))
            if kwargs is None: kwargs = {}
            dict(A=subsys.add_action_by_name,
                 P=subsys.add_parameter_by_name)[typ](
                     name.lower(), getcmd,
                     **({} if kwargs is None else kwargs))


class ScpiInstrumentMinimal(ScpiInstrument):

    """`ScpiInstrument` implementing required SCPI commands."""

    def __init__(self, socket):
        super(ScpiInstrumentMinimal, self).__init__(socket, ScpiProtocol())
        self.ieee488_2 = Ieee488_2(IeeeProtocol())
        self.add_subsystems_from_tree(yaml.load(
            # required commands:
            """
            SYSTem:
              P_ERRor:
              P_VERSion:
            STATus:
              OPERation:
                &leaves
                P_CONDition:
                P_ENABle: {read_only: true}
                P_EVENt:
              A_PRESet:
              QUESTionable:
                *leaves
            """))


# SCPI Instrument Classes - 3 Digital Meters
class ScpiDigitalMeter(ScpiInstrumentMinimal):

    """Base functionality of a digital meter."""

    def __init__(self, socket, meter_fun):
        super(ScpiDigitalMeter, self).__init__(socket)
        # Base measurement instructions
        self.add_subsystems_from_tree(yaml.load(
        """
        CONFigure:
          SCALar:
            P_%(meter_fun)s:
        FETCh:
          &scalar
          SCALar:
            P_%(meter_fun)s: {read_only: true}
        READ:
          *scalar
        MEASure:
          *scalar
        """ % {"meter_fun": meter_fun}))
        # Base device-oriented functions
        self.add_subsystems_from_tree(yaml.load(
        """
        # SENSe subsystem
        SENSe:
          FUNCtion:
            ON: function
            %(meter_fun)s:
              RANGe:
                P_UPPer_range: # num
                P_AUTO_range:  # bool
              RESolution # num
        # TRIGger subsystem
        #INITitiate:
        #  IMM:
        #    A_ALL: initiate_trigger  # write-only
        #A_ABORt: abort_trigger  # write-only
        TRIGger:
          SEQuence:
            P_COUNt:  # num
            P_DELay:  # num
            P_SOURce: # str
        """ % {"meter_fun": meter_fun}))


class ScpiDCVoltmeter(ScpiDigitalMeter):

    def __init__(self, socket):
        super(ScpiDCVoltmeter, self).__init__(socket, "VOLT")
        # SENSe: see Command Ref 18.20


class ScpiACVoltmeter(ScpiDigitalMeter):
    
    def __init__(self, socket):
        super(ScpiACVoltmeter, self).__init__(socket, "VOLT:AC")


class ScpiDCAmmeter(ScpiDigitalMeter):
    
    def __init__(self, socket):
        super(ScpiDCAmmeter, self).__init__(socket, "CURR")


class ScpiACAmmeter(ScpiDigitalMeter):

    def __init__(self, socket):
        super(ScpiACAmmeter, self).__init__(socket, "CURR:AC")


class ScpiOhmmeter(ScpiDigitalMeter):
    
    def __init_(self, socket):
        super(ScpiOhmmeter, self).__init__(socket, "RES")


class ScpiFourWireOhmmeter(ScpiDigitalMeter):

    def __init__(self, socket):
        super(ScpiFourWireOhmmeter, self).__init__(socket, "FRES")


# SCPI Instrument Classes - 7 Power Supplies
class ScpiPowerSupply(ScpiInstrumentMinimal):

    def __init__(self, socket):
        super(ScpiPowerSupply, self).__init__(socket)
        self.add_subsystems_from_tree(yaml.load(
            """
            OUTPUT:
              P_STATe # bool //FIXME// status?
            SOURce:
                &cv
                P_CURRent:
                P_VOLTage:
            STATus:
              QUEST:
                *cv
              # bit 1 for current; bit 0 for voltage; bit 0+1 for both
            MEASure:
                *cv
              # multiple
              # trigger
            """))


def _test():
    instr = ScpiInstrumentMinimal(drv.Serial())
    print(instr)
    print("\nSTAT:")
    print(instr.status)
    print("\nQUEST:")
    print(instr.status.questionable)
    print("\nOPER:")
    print(instr.status.operation)


if __name__ == "__main__":
    _test()

