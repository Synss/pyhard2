# vim: tw=120
"""Drivers for Bronkhorst flow and pressure controllers.

Communication uses the ASCII protocol described in the instruction
manual number 9.17.027.  The commands and subsystems are described in
the instruction manual number 9.17.023.

Note:
    - The ASCII protocol is implemented.
    - This driver requires the `Construct library
      <http://construct.readthedocs.org/en/latest/>`_.

Reference:
    - `"RS232 interface with FLOW-BUS protocol for digital Mass
      Flow/Pressure instruments." <http://www.bronkhorst.com>`_
      Doc. no.: 9.17.027J 13-05-2008.
    - `"Operation instructions digital Mass Flow/Pressure instruments
      parameters and properties." <http://www.bronkhorst.com>`_
      Doc. no.: 9.17.023L 27-05-2008.

"""
import unittest
import logging

import pyhard2.driver as drv
Access = drv.Access

from _bronkhorst import read_command, write_command
from _bronkhorst import status_message, extract_values, float2long


logging.basicConfig()
logger = logging.getLogger("pyhard2")


class BronkhorstHardwareError(drv.HardwareError): pass


class BronkhorstDriverError(drv.DriverError): pass


def _measure_to_pct(x):
    if x >= 41943:
        x -= 65536
    return float(x) / 320.0

def _pct_to_measure(x):
    x = int(round(x * 320.0))
    if x < 0:
        x += 65536
    return x

def _valve_output_to_pct(x):
    return x / 167772.15

def _pct_to_valve_output(x):
    return int(round(x * 167772.15))


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


CHAR = 'c'
UINT = 'i'
FLOAT = 'f'
ULONG = 'l'
STRING = 's'


class _BHParameter(object):

    """API for `Construct <http://construct.wikispaces.com/>`_."""

    index = 0

    def __init__(self, number, type, parent=None, value=None, chained=False):
        self.number = number
        self.type = type
        self.parent = parent
        self.value = value
        self.chained = chained
        self.string_length = 0
        if parent:
            # READ repeats process
            self.process = _BHProcess(parent.number, parent.chained)
            # READ contains index
            self.idx = _BHParameter(
                    _BHParameter.index, self.type, self.chained)
            _BHParameter.index += 1
            _BHParameter.index %= 31

    def __repr__(self):
        return "%s(number=%s, type=%s, parent=%s, value=%r, chained=%s)" % (
            self.__class__.__name__,
            self.number, self.type, self.parent, self.value, self.chained)


class _BHProcess(object):

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
    def from_param(cls, process_number, cmd, value=None):
        process = _BHProcess(process_number)
        process.param_list = [_BHParameter(
            cmd.reader, cmd.type, parent=process, value=value)]
        return process

    @classmethod
    def from_default_process(cls, number, type, value=None, chained=False):
        process = _BHProcess(1)
        process.param_list = [_BHParameter(
            number, type, parent=process, value=value, chained=False)]
        return process


class _BHProcessList(object):

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
        soft_init = _BHProcess(0, [_BHParameter(10, type=CHAR, value=0x40)])
        reset_init = _BHProcess(0, [_BHParameter(10, type=CHAR, value=0x52)])
        process_list, self.process_list = self.process_list, [soft_init]
        for process in process_list:
            self.append_process(process)
        self.append_process(reset_init)


class AsciiProtocol(drv.CommunicationProtocol):

    """ASCII protocol."""

    def __init__(self, socket):
        super(AsciiProtocol, self).__init__(socket)

    err = {":0101": "no ':' at the start of the message",
           ":0102": "error in first byte",
           ":0103": "error in second byte (length)",
           ":0104": "error in received message",
           ":0105": "Flowbus communication error",
           ":0108": "timeout during sending",
           ":0109": "no answer received within timeout"}

    def read(self, context):
        subsys, cmd = context.path[0], context._command
        msg = _BHProcessList(context.node, "read",
                             [_BHProcess.from_param(subsys.process, cmd)])
        msg.length = (len(read_command.build(msg)) - 5) / 2
        type_ = cmd.type
        self._socket.write(read_command.build(msg))
        ans = self._socket.readline()
        try:
            #return filter(lambda ppv: 
            #              ppv not in [(1, 10, 0x40),   # soft init
            #                          (1, 10, 0x52)],  # reset init
            #              extract_values(ans))
            vals = [val for process, cmd, val in extract_values(ans)]
            if len(vals) is 1:
                val = vals.pop()
                # Float and long have the same enum in this protocol
                # there is no way to check which type we have earlier.
                # We check it here.
                return float2long(val) if type_ == "l" else val
            else:
                return vals
        except:
            # format is not WRITE, check STATUS
            self._check_error(msg, ans)

    def write(self, context):
        subsys, cmd, value = context.path[0], context._command, context.value
        msg = _BHProcessList(context.node, "write",
                            [_BHProcess.from_param(subsys.process,
                                                  cmd, value)])
        if cmd.secured and not cmd.access == Access.RO:
            msg.lift_security()
        msg.length = (len(write_command.build(msg)) - 5) / 2
        self._socket.write(write_command.build(msg))
        ans = self._socket.readline()
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
                "Node %i: Command %r returned error: %s" %
                (msg.node, msg,
                 AsciiProtocol.err.get(ans.strip(), "unknown message %r" % ans)))


class Subsystem(drv.Subsystem):

    """Subsystem with process number."""

    def __init__(self, process, parent=None):
        super(Subsystem, self).__init__(parent)
        self.process = process


class Cmd(drv.Command):

    """`Command` with parameters `type` and `secured`.

    Parameters:
        type (str): {CHAR, UINT, FLOAT, ULONG, STRING}
            Parameter type.
        secured (bool): True if parameter is secured.

    """
    def __init__(self, reader, type=None, secured=False, **kwargs):
        super(Cmd, self).__init__(reader, **kwargs)
        self.type = type
        self.secured = secured
        if secured:
            self.access = Access.RO


class Controller(Subsystem):

    """Driver for Bronkhorst controllers.

    Note:
        Node 128 broadcasts to every node.

    .. graphviz:: gv/Controller.txt

    """
    def __init__(self, socket):
        socket.baudrate = 38400
        socket.timeout = 3
        super(Controller, self).__init__(1)
        self.setProtocol(AsciiProtocol(socket))
        # Process 1
        self.measure = Cmd(0, rfunc=_measure_to_pct, wfunc=_pct_to_measure,
                           access=Access.RO, type=UINT)
        self.setpoint = Cmd(1, rfunc=_measure_to_pct, wfunc=_pct_to_measure,
                            minimum=0, maximum=3200, type=UINT)
        self.setpoint_slope = Cmd(2, minimum=0, maximum=30000, type=UINT)
        self.analog_input = Cmd(3, type=UINT)
        self.control_mode = Cmd(4, minimum=0, maximum=255, type=CHAR)
        #init = Cmd(10, minimum=0, maximum=255, type=CHAR)
        self.fluid_ptr = Cmd(16, minimum=0, maximum=7, type=CHAR)
        self.fluid = Cmd(17, type=STRING, secured=True)
        self.info = Cmd(20, type=CHAR)
        self.capacity_100pct = Cmd(13, minimum=0.0, type=FLOAT, secured=True)
        self.sensor_type = Cmd(14, minimum=0, maximum=4, type=CHAR, secured=True)
        self.capacity_unit_ptr = Cmd(15, minimum=0, maximum=9, type=CHAR, secured=True)
        self.capacity_unit = Cmd(31, type=STRING, secured=True)
        # Direct reading subsystem, process 33
        self.direct_reading = Subsystem(33, self)
        self.direct_reading.capacity_0pct = Cmd(22, type=FLOAT, secured=True)
        self.direct_reading.measure = Cmd(0, access=Access.RO, type=FLOAT)
        self.direct_reading.setpoint = Cmd(3, type=FLOAT)
        self.direct_reading.master_slave_ratio = Cmd(1, minimum=0, maximum=500, type=FLOAT)
        # Identification subsystem, process 113
        self.identification = Subsystem(113, self)
        self.identification.model_number = Cmd(2, type=STRING)
        self.identification.serial_number = Cmd(3, type=STRING)
        self.identification.config_string = Cmd(4, type=STRING, secured=True)
        self.identification.firmware = Cmd(5, type=STRING)
        self.identification.usertag = Cmd(6, type=STRING, secured=True)
        self.identification.device_type_ptr = Cmd(12, type=CHAR)
        # Alarm/status parameters subsystem, process 97
        self.alarm = Subsystem(97, self)
        self.alarm.max_limit = Cmd(1, minimum=0, maximum=32000, type=UINT, secured=True)
        self.alarm.min_limit = Cmd(2, minimum=0, maximum=32000, type=UINT, secured=True)
        self.alarm.mode = Cmd(3, minimum=0, maximum=3, type=CHAR, secured=True)
        self.alarm.output_mode = Cmd(4, minimum=0, maximum=2, type=CHAR, secured=True)
        self.alarm.setpoint_mode = Cmd(5, minimum=0, maximum=1, type=CHAR, secured=True)
        self.alarm.new_setpoint = Cmd(6, minimum=0, maximum=32000, type=UINT, secured=True)
        self.alarm.delay_time = Cmd(7, minimum=0, maximum=255, type=CHAR, secured=True)
        #self.alarm.reset = Cmd(process=115, param=4, minimum=0, maximum=15, type=CHAR, secured=True)
        # Counter subsystem, process 104
        self.counter = Subsystem(104, self)
        self.counter.value = Cmd(1, minimum=0.0, maximum=1e+07, type=FLOAT, secured=True)
        self.counter.unit_ptr = Cmd(2, minimum=0, maximum=13, type=CHAR, secured=True)
        self.counter.limit = Cmd(3, minimum=0.0, maximum=1e+07, type=FLOAT, secured=True)
        self.counter.output_mode = Cmd(4, minimum=0, maximum=2, type=CHAR, secured=True)
        self.counter.setpoint_mode = Cmd(5, minimum=0, maximum=1, type=CHAR, secured=True)
        self.counter.new_setpoint = Cmd(6, minimum=0, maximum=32000, type=UINT, secured=True)
        self.counter.unit = Cmd(7, type=STRING)
        self.counter.mode = Cmd(8, minimum=0, maximum=2, type=CHAR, secured=True)
        # Controller subsystem, process 114
        self.controller = Subsystem(114, self)
        self.controller.valve_output = Cmd(1, minimum=0, maximum=100,
                                           rfunc=_valve_output_to_pct, wfunc=_pct_to_valve_output,
                                           type=ULONG, secured=True)
        self.controller.response_on_setpoint_change = Cmd(5, minimum=0, maximum=255, type=CHAR, secured=True)
        self.controller.response_when_stable = Cmd(17, minimum=0, maximum=255, type=CHAR, secured=True)
        self.controller.response_on_startup = Cmd(18, minimum=0, maximum=255, type=CHAR, secured=True)
        self.controller.PIDKp = Cmd(21, minimum=0.0, maximum=1e+10, type=FLOAT, secured=True)
        self.controller.PIDKi = Cmd(22, minimum=0.0, maximum=1e+10, type=FLOAT, secured=True)
        self.controller.PIDKd = Cmd(23, minimum=0.0, maximum=1e+10, type=FLOAT, secured=True)  ## double check
        #self.controller.TDS_up = Cmd(param=12, minimum=0.0, maximum=1e+10, type=FLOAT, secured=True)
        #self.controller.TDS_down = Cmd(param=11, minimum=0.0, maximum=1e+10, type=FLOAT, secured=True)
        #self.controller.smoothing = Cmd(process=117, param=4, minimum=0.0, maximum=1.0, type=FLOAT, secured=True)
        #self.controller.smoothing_rate = Cmd(process=117, param=5, minimum=0.0, maximum=1.0, type=FLOAT, secured=True)

    def response(self, status, value):
        {"setpoint": self.response_on_setpoint_change,
         "steady state": self.response_when_stable,
         "startup": self.response_on_startup}[status] = value

        # set minimum, maximum values for setpoint
        self.direct_reading.setpoint.minimum = self.direct_reading.capacity_0pct
        self.direct_reading.setpoint.maximum = self.capacity_100pct


class MFC(Controller):

    """Instrument for mass-flow controllers."""

    def __init__(self, socket):
        super(MFC, self).__init__(socket)


class PC(Controller):

    """Instrument for pressure controllers."""

    def __init__(self, socket):
        super(PC, self).__init__(socket)


class BronkhorstTest(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {
            # example 3.10.1: set setpoint node 3 to 50%
            ":06030101213E80\r\n": ":0403000005\r\n",
            # example 3.10.3: request setpoint node 3 (-> 50%)
            ":06030401210121\r\n": ":06030201213E80\r\n",
            # 3.10.5: request measure from node 3 (50%)
            ":06030401220120\r\n": ":06030201213E80\r\n",
            # request counter value from node 3, process 104, float
            ":06030468436841\r\n": ":0803026841459cffae\r\n",
        }
        self.i = Controller(socket)

    # manual 917027, examples pp. 18-24
    def test_3_10_1(self):
        # send SP (node 3, process 1, param 1, int = 16000)
        self.i.setpoint.write(50, node=3)
        self.assertDictEqual(status_message.parse(":0403000005\r\n"),
                             dict(length=4, node=3, command="status",
                                  status="no_error", byte_index=5))

    def test_3_10_3(self):
        # req SP (node 3, process 1, param 1, int)
        self.assertEqual(self.i.setpoint.read(node=3), 50.0)

    def test_3_10_5(self):
        self.assertEqual(self.i.measure.read(node=3), 50.0)

    def test_float(self):
        self.assertAlmostEqual(self.i.counter.value.read(node=3), 5023.96, 2)

    def test_chained_write_message_parser(self):
        write_command.parse(''.join((
            ':',
            '1d0301',
            '80',             # process 1
            '0a40',           # param   1.1
            '81',             # process 2
            'c500000000',     # param   2.1
            'c63f800000',     # param   2.2
            'c700000000',     # param   2.3
            '4800000000',     # param   2.4 <- chained in manual
            '00',             # process 3
            '0a52',           # param   3.1
            '\r\n')))

    def test_chained_read_parser(self):
        read_command.parse(''.join((':',
                                    '1a0304f1ec7163146d716600',
                                    '01ae0120cf014df0017f0771',
                                    '01710a\r\n')))   # <-- original

    def test_chained_read_parser_answer(self):
        write_command.parse(''.join((
            ':',
            '410302',
            'f1',                    # process 1
            'ec14'                   # param   1.1
            '4d363231323334354120',  # value   1.1
            '20202020202020202020',
            '6d00',                  # param   1.2
            '5553455254414700',      # value   1.2
            '01',                    # process 2
            'ae',                    # param   2.1
            '1cd8',                  # value   2.1
            'cf',                    # param   2.2
            '3f800000',              # value   2.2
            'f007',                  # param   2.3
            '6d6c6e2f6d696e',        # value   2.3
            '710a',                  # param   2.4
            '4e322020202020202020',  # value   2.4
            '\r\n')))


if __name__ == "__main__":
    unittest.main()

