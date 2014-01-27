"""
Bronkhorst drivers
==================

Drivers for Bronkhorst flow and pressure controllers.

Communication uses the ASCII protocol described in the instruction manual
number 9.17.027. [1]_  The commands and subsystems are described in the
instruction manual number 9.17.023. [2]_

Notes
-----
- The ASCII protocol is implemented.
- This driver requires the `Construct library
  <http://construct.readthedocs.org/en/latest/>`_.

References
----------
.. [1] `"RS232 interface with FLOW-BUS protocol for digital Mass
        Flow/Pressure instruments." <http://www.bronkhorst.com>`_ Doc.
        no.: 9.17.027J 13-05-2008.
.. [2] `"Operation instructions digital Mass Flow/Pressure instruments
        parameters and properties." <http://www.bronkhorst.com>`_ Doc.
        no.: 9.17.023L 27-05-2008.

"""

import logging

import pyhard2.driver as drv

from _bronkhorst import read_command, write_command
from _bronkhorst import status_message, extract_values


logging.basicConfig()
logger = logging.getLogger("pyhard2")


class BronkhorstHardwareError(drv.HardwareError): pass


class BronkhorstDriverError(drv.DriverError): pass


def measure_to_pct(x):
    if x >= 41943:
        x -= 65536
    return float(x) / 320.0

def pct_to_measure(x):
    x = int(round(x * 320.0))
    if x < 0:
        x += 65536
    return x


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


CHAR = 'c'
UINT = 'i'
FLOAT = 'f'
ULONG = 'l'
STRING = 's'


class BHParameter(object):

    """API for `Construct <http://construct.wikispaces.com/>`_."""

    index = 10

    def __init__(self, number, type, parent=None, value=None, chained=False):
        self.number = number
        self.type = type
        self.parent = parent
        self.value = value
        self.chained = chained
        self.string_length = 0
        if parent:
            # READ repeats process
            self.process = BHProcess(parent.number, parent.chained)
            # READ contains index
            self.idx = BHParameter(
                    BHParameter.index, self.type, self.chained)
            BHParameter.index += 1
            BHParameter.index %= 255

    def __repr__(self):
        return "%s(number=%s, type=%s, parent=%s, value=0x%x, chained=%s)" % (
            self.__class__.__name__,
            self.number, self.type, self.parent, self.value, self.chained)


class BHProcess(object):

    """API for `Construct <http://construct.wikispaces.com/>`_."""

    def __init__(self, number, param_list=None, chained=False):
        self.number = number
        self.param_list = param_list
        self.chained = chained

    def __repr__(self):
        return "%s(number=%s, param_list=%s, chained=%s)" % (
            self.__class__.__name__,
            self.number, self.param_list, self.chained)

    @classmethod
    def from_param(cls, process_number, param, value=None):
        process = BHProcess(process_number)
        process.param_list = [BHParameter(
            param.getcmd, param.type, parent=process, value=value)]
        return process

    @classmethod
    def from_default_process(cls, number, type, value=None, chained=False):
        process = BHProcess(1)
        process.param_list = [BHParameter(
            number, type, parent=process, value=value, chained=False)]
        return process


class BHProcessList(object):

    """API for `Construct <http://construct.wikispaces.com/>`_."""

    def __init__(self, node, command, process_list=None):
        self.node = node
        self.command = command
        self.length = 0
        self.index = 12
        self.process_list = []
        for process in process_list:
            self.append_process(process)

    def __repr__(self):
        return "%s(node=%s, command=%s, process_list=%s)" % (
            self.__class__.__name__,
            self.node, self.command, self.process_list)

    def append_process(self, process):
        """Buffer process

        - check at which level to chain (parameter/process)
        - set `chained` flag appropriately

        """
        if self.process_list:
            if self.process_list[-1].number == process.number:
                # chain parameters
                self.process_list[-1].param_list[-1].chained = True
                self.process_list[-1].param_list.extend(process.param_list)
            else:
                # chain processes
                self.process_list[-1].chained = True
                self.process_list.append(process)
        else:  # no process_list, create one
            self.process_list = [process]

    def lift_security(self):
        """Add `soft_init` and `reset_init` to the process_list."""
        soft_init = BHProcess(0, [BHParameter(10, type=CHAR, value=0x40)])
        reset_init = BHProcess(0, [BHParameter(10, type=CHAR, value=0x52)])
        process_list, self.process_list = self.process_list, [soft_init]
        for process in process_list:
            self.append_process(process)
        self.append_process(reset_init)


class Param(drv.Parameter):

    """
    `Parameter` extended with `type` and `secured`

    Parameters
    ----------
    type : {CHAR, UINT, FLOAT, ULONG, STRING}
        Parameter type.
    secured : bool
        True if parameter is secured.

    """

    def __init__(self, getcmd, type=None, secured=False, **kwargs):
        super(Param, self).__init__(getcmd, **kwargs)
        self.type = type
        self.secured = secured
        if secured:
            self.read_only = secured


class AsciiProtocol(drv.SerialProtocol):

    """ASCII protocol."""

    def __init__(self, socket, async, node):
        super(AsciiProtocol, self).__init__(socket, async)
        self.node = node

    err = {":0101": "no ':' at the start of the message",
           ":0102": "error in first byte",
           ":0103": "error in second byte (length)",
           ":0104": "error in received message",
           ":0105": "Flowbus communication error",
           ":0108": "timeout during sending",
           ":0109": "no answer received within timeout"}

    def _encode_read(self, subsys, param):
        msg = BHProcessList(self.node, "read",
                            [BHProcess.from_param(subsys.process, param)])
        msg.length = (len(read_command.build(msg)) - 5) / 2
        self.socket.write(read_command.build(msg))
        ans = self.socket.readline()
        try:
            #return filter(lambda ppv: 
            #              ppv not in [(1, 10, 0x40),   # soft init
            #                          (1, 10, 0x52)],  # reset init
            #              extract_values(ans))
            vals = [val for process, param, val in extract_values(ans)]
            if len(vals) is 1:
                return vals.pop()
            else:
                return vals
        except:
            # format is not WRITE, check STATUS
            self._check_error(msg, ans)

    def _encode_write(self, subsys, param, value):
        msg = BHProcessList(self.node, "write",
                            [BHProcess.from_param(subsys.process,
                                                  param, value)])
        if param.secured and not param.read_only:
            msg.lift_security()
        msg.length = (len(write_command.build(msg)) - 5) / 2
        self.socket.write(write_command.build(msg))
        ans = self.socket.readline()
        self._check_error(msg, ans)

    @staticmethod
    def _check_error(msg, ans):
        try:
            # Assume ans is STATUS message
            status = status_message.parse(ans)
            if not status.status.startswith("no_error"):
                status_msg = " ".join(status.status.split("_"))
                #logger.warning(status_msg)
                raise BronkhorstHardwareError(
                    "Node %i: Command %s returned status: %s" %
                    (msg.node, msg, status_msg))
        except BronkhorstHardwareError:
            # We are done with it, reraise
            raise
        except Exception:
            # not a STATUS message, assume PROTOCOL error or UNKNOWN
            raise BronkhorstHardwareError(
                "Node %i: Command %s returned error: %s" %
                (msg.node, msg,
                 AsciiProtocol.err.get(ans.strip(),
                                       "unknown message %s" % ans.strip())))


class Subsystem(drv.Subsystem):

    """Subsystem with process number."""

    def __init__(self, protocol, process):
        super(Subsystem, self).__init__(protocol)
        self.process = process


class NormalSubsystem(Subsystem):

    """Normal operation parameters."""

    ## fget(proc, reg, unit=UINT, secured=False)
    ## fset(proc, reg, minx, maxx, unit=UINT, secured=False)

    measure = Param(0, getter_func=measure_to_pct,
                       setter_func=pct_to_measure,
                       read_only=True, type=UINT)
    setpoint = Param(1, getter_func=measure_to_pct, 
                        setter_func=pct_to_measure,
                        minimum=0, maximum=3200, type=UINT)
    setpoint_slope = Param(2, minimum=0, maximum=30000, type=UINT)
    analog_input = Param(3, type=UINT)
    control_mode = Param(4, minimum=0, maximum=255, type=CHAR)
    #init = Param(10, minimum=0, maximum=255, type=CHAR)
    fluid_ptr = Param(16, minimum=0, maximum=7, type=CHAR)
    fluid = Param(17, type=STRING, secured=True)
    info = Param(20, type=CHAR)
    capacity_100pct = Param(13, minimum=0.0, type=FLOAT, secured=True)
    sensor_type = Param(14, minimum=0, maximum=4, type=CHAR, secured=True)
    capacity_unit_ptr = Param(15, minimum=0, maximum=9, type=CHAR, secured=True)
    capacity_unit = Param(31, type=STRING, secured=True)


class DirectReadingSubsystem(Subsystem):

    """Direct reading parameters."""

    capacity_0pct = Param(22, type=FLOAT, secured=True)
    fmeasure = Param(0, read_only=True, type=FLOAT)
    fsetpoint = Param(3, type=FLOAT)
    master_slave_ratio = Param(1, minimum=0, maximum=500, type=FLOAT)


class IdentificationSubsystem(Subsystem):

    """Identification parameters."""

    model_number = Param(2, type=STRING)
    serial_number = Param(3, type=STRING)
    config_string = Param(4, type=STRING, secured=True)
    firmware = Param(5, type=STRING)
    usertag = Param(6, type=STRING, secured=True)
    device_type_ptr = Param(12, type=CHAR)


class AlarmSubsystem(Subsystem):

    """Alarm/status parameters."""

    max_limit = Param(1, minimum=0, maximum=32000, type=UINT, secured=True)
    min_limit = Param(2, minimum=0, maximum=32000, type=UINT, secured=True)
    mode = Param(3, minimum=0, maximum=3, type=CHAR, secured=True)
    output_mode = Param(4, minimum=0, maximum=2, type=CHAR, secured=True)
    setpoint_mode = Param(5, minimum=0, maximum=1, type=CHAR, secured=True)
    new_setpoint = Param(6, minimum=0, maximum=32000, type=UINT, secured=True)
    delay_time = Param(7, minimum=0, maximum=255, type=CHAR, secured=True)

    #reset = Param(process=115, param=4, minimum=0, maximum=15,
    #              type=CHAR, secured=True)


class CounterSubsystem(Subsystem):

    """Counter parameters."""

    value = Param(1, minimum=0.0, maximum=1e+07, type=FLOAT, secured=True)
    unit_ptr = Param(2, minimum=0, maximum=13, type=CHAR, secured=True)
    limit = Param(3, minimum=0.0, maximum=1e+07, type=FLOAT, secured=True)
    output_mode = Param(4, minimum=0, maximum=2, type=CHAR, secured=True)
    setpoint_mode = Param(5, minimum=0, maximum=1, type=CHAR, secured=True)
    new_setpoint = Param(6, minimum=0, maximum=32000, type=UINT, secured=True)
    unit = Param(7, type=STRING)
    mode = Param(8, minimum=0, maximum=2, type=CHAR, secured=True)


class ControllerSubsystem(Subsystem):

    """Controller parameters."""

    valve_output = Param(1, minimum=0, maximum=16777215,
                         type=ULONG, secured=True)
    response_on_setpoint_change = Param(5, minimum=0, maximum=255,
                                        type=CHAR, secured=True)
    response_when_stable = Param(17, minimum=0, maximum=255,
                                 type=CHAR, secured=True)
    response_on_startup = Param(18, minimum=0, maximum=255,
                                type=CHAR, secured=True)
    PIDKp = Param(21, minimum=0.0, maximum=1e+10, type=FLOAT, secured=True)
    PIDKi = Param(22, minimum=0.0, maximum=1e+10, type=FLOAT, secured=True)
    PIDKd = Param(23, minimum=0.0, maximum=1e+10, type=FLOAT, secured=True)  ## double check

    #TDS_up = Param(param=12, minimum=0.0, maximum=1e+10, type=FLOAT, secured=True)
    #TDS_down = Param(param=11, minimum=0.0, maximum=1e+10, type=FLOAT, secured=True)
    #smoothing = Param(process=117, param=4, minimum=0.0, maximum=1.0, type=FLOAT,
    #                  secured=True)
    #smoothing_rate = Param(process=117, param=5, minimum=0.0, maximum=1.0,
    #                       type=FLOAT, secured=True)

    def response(self, status, value):
        {"setpoint": self.response_on_setpoint_change,
         "steady state": self.response_when_stable,
         "startup": self.response_on_startup}[status] = value


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class ControllerInstr(drv.Instrument):

    """
    Instrument for Bronkhorst controllers.

    Parameters
    ----------
    socket
    node : int
        The instrument node or 128 to broadcast the commands.

    """

    def __init__(self, socket, async=False, node=128):
        super(ControllerInstr, self).__init__()

        socket.baudrate = 38400
        socket.timeout = 3

        protocol = AsciiProtocol(socket, async, node)

        self.main = NormalSubsystem(protocol, 1)
        self.direct_reading = DirectReadingSubsystem(protocol, 33)
        self.identification = IdentificationSubsystem(protocol, 113)
        self.alarm = AlarmSubsystem(protocol, 97)
        self.counter = CounterSubsystem(protocol, 104)
        self.controller = ControllerSubsystem(protocol, 114)

    #_wink = Param()

    def wink(self):
        pass

    #_reset = Param()

    def reset(self):
        pass

    #@node.setter
    #def node(self, val):
    #    self._node = self._node if self._node > 3 else 3
    #    self._node = self._node if self._node < 128 else 128
    #    # propagate change:
    #    for obj in self.__dict__.values():
    #        if isinstance(obj, Subsystem):
    #            obj.node = self._node


class MFC(ControllerInstr):
    """Instrument for mass-flow controllers."""

    def __init__(self, socket, async=False, node=128):
        super(MFC, self).__init__(socket, async, node)


class PC(ControllerInstr):
    """Instrument for pressure controllers."""

    def __init__(self, socket, async=False, node=128):
        super(PC, self).__init__(socket, async, node)


class _FakeSocket(object):

    status = ':\x04\x03\x00\x00\x1c\r\n'
    ans1 = ''.join((':',
                    '\x1d\x03\x01\x80\x0a\x40\x81\xc5\x00\x00\x00\x00',
                    '\xc6\x3f\x80\x00\x00\xc7\x00\x00\x00\x00',
                    '\x48\x00\x00\x00\x00\x00\x0a\x52\r\n'))

    def __init__(self, port):
        pass

    def getter(self, cmd):
        print("getter: %s" % cmd)
        return _FakeSocket.ans1

    def setter(self, cmd):
        print("setter: %s" % cmd)
        return _FakeSocket.status

