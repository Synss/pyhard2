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
from binascii import hexlify, unhexlify

import pyhard2.driver as drv

from ._bronkhorst import Reader, Writer, Status, ValidationError


class BronkhorstHardwareError(drv.HardwareError): pass


class BronkhorstDriverError(drv.DriverError): pass


class Access(drv.Access):

    """Access enum with SEC access for secured commands.

    Attributes:
        RO, WO, RW, SEC

    """
    SEC = "Access.SEC"


class Subsystem(drv.Subsystem):

    """Subsystem with process number."""

    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process


class Cmd(drv.Command):

    """`Command` with a `type` attributes.

    Parameters:
        type (str): {CHAR, UINT, FLOAT, ULONG, STRING}
            Parameter type.

    """
    class Context(drv.Context):

        """`Context` with a `type` attribute."""

        def __init__(self, command, value=None, node=None):
            super().__init__(command, value, node)
            self.type = command.type

    def __init__(self, reader, type=None, **kwargs):
        super().__init__(reader, **kwargs)
        self.type = type


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


CHAR = 'c'
UINT = 'i'
FLOAT = 'f'
ULONG = 'l'
STRING = 's'


class AsciiProtocol(drv.CommunicationProtocol):

    """ASCII protocol."""

    def __init__(self, socket):
        super().__init__(socket)

    err = {":0101": "no ':' at the start of the message",
           ":0102": "error in first byte",
           ":0103": "error in second byte (length)",
           ":0104": "error in received message",
           ":0105": "Flowbus communication error",
           ":0108": "timeout during sending",
           ":0109": "no answer received within timeout"}

    @staticmethod
    def toAscii(bytes_):
        return ":%s\r\n" % hexlify(bytes_).upper()

    @staticmethod
    def toBytes(ascii_):
        return unhexlify(ascii_[1:-2])  # do not convert ":" and "\r\n"

    def read(self, context):
        construct = Reader.fromContext(context)
        self._socket.write(self.toAscii(construct.build()))
        ans = self._socket.readline()
        try:
            return Writer.parse(self.toBytes(ans), context.type).value
        except ValidationError:
            # format is not WRITE, check STATUS
            self._check_error(construct, ans)

    def write(self, context):
        construct = Writer.fromContext(context)
        self._socket.write(self.toAscii(construct.build()))
        ans = self._socket.readline()
        self._check_error(construct, ans)

    @staticmethod
    def _check_error(construct, ans):
        try:
            # Assume ans is STATUS message
            status = Status.parse(AsciiProtocol.toBytes(ans))
            if not status.startswith("no_error"):
                status_msg = " ".join(status.split("_"))
                raise BronkhorstHardwareError(
                    "Node %i: Command %s returned status: %s" %
                    (construct.node, construct, status_msg))
        except BronkhorstHardwareError:
            # We are done with it, reraise
            raise
        except Exception:
            # not a STATUS message, assume PROTOCOL error or UNKNOWN
            raise BronkhorstHardwareError(
                "Node %i: Command %r returned error: %s" %
                (construct.node, construct,
                 AsciiProtocol.err.get(ans.strip(), "unknown message %r" % ans)))


class Controller(Subsystem):

    """Driver for Bronkhorst controllers.

    Note:
        Node 128 broadcasts to every node.

    .. graphviz:: gv/Controller.txt

    """
    def __init__(self, socket):
        socket.baudrate = 38400
        socket.timeout = 3
        super().__init__(1)
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
        self.fluid = Cmd(17, type=STRING, access=Access.SEC)
        self.info = Cmd(20, type=CHAR)
        self.capacity_100pct = Cmd(13, minimum=0.0, type=FLOAT, access=Access.SEC)
        self.sensor_type = Cmd(14, minimum=0, maximum=4, type=CHAR, access=Access.SEC)
        self.capacity_unit_ptr = Cmd(15, minimum=0, maximum=9, type=CHAR, access=Access.SEC)
        self.capacity_unit = Cmd(31, type=STRING, access=Access.SEC)
        # Direct reading subsystem, process 33
        self.direct_reading = Subsystem(33, self)
        self.direct_reading.capacity_0pct = Cmd(22, type=FLOAT, access=Access.SEC)
        self.direct_reading.measure = Cmd(0, access=Access.RO, type=FLOAT)
        self.direct_reading.setpoint = Cmd(3, type=FLOAT)
        self.direct_reading.master_slave_ratio = Cmd(1, minimum=0, maximum=500, type=FLOAT)
        # Identification subsystem, process 113
        self.identification = Subsystem(113, self)
        self.identification.model_number = Cmd(2, type=STRING)
        self.identification.serial_number = Cmd(3, type=STRING)
        self.identification.config_string = Cmd(4, type=STRING, access=Access.SEC)
        self.identification.firmware = Cmd(5, type=STRING)
        self.identification.usertag = Cmd(6, type=STRING, access=Access.SEC)
        self.identification.device_type_ptr = Cmd(12, type=CHAR)
        # Alarm/status parameters subsystem, process 97
        self.alarm = Subsystem(97, self)
        self.alarm.max_limit = Cmd(1, minimum=0, maximum=32000, type=UINT, access=Access.SEC)
        self.alarm.min_limit = Cmd(2, minimum=0, maximum=32000, type=UINT, access=Access.SEC)
        self.alarm.mode = Cmd(3, minimum=0, maximum=3, type=CHAR, access=Access.SEC)
        self.alarm.output_mode = Cmd(4, minimum=0, maximum=2, type=CHAR, access=Access.SEC)
        self.alarm.setpoint_mode = Cmd(5, minimum=0, maximum=1, type=CHAR, access=Access.SEC)
        self.alarm.new_setpoint = Cmd(6, minimum=0, maximum=32000, type=UINT, access=Access.SEC)
        self.alarm.delay_time = Cmd(7, minimum=0, maximum=255, type=CHAR, access=Access.SEC)
        #self.alarm.reset = Cmd(process=115, param=4, minimum=0, maximum=15, type=CHAR, access=Access.SEC)
        # Counter subsystem, process 104
        self.counter = Subsystem(104, self)
        self.counter.value = Cmd(1, minimum=0.0, maximum=1e+07, type=FLOAT, access=Access.SEC)
        self.counter.unit_ptr = Cmd(2, minimum=0, maximum=13, type=CHAR, access=Access.SEC)
        self.counter.limit = Cmd(3, minimum=0.0, maximum=1e+07, type=FLOAT, access=Access.SEC)
        self.counter.output_mode = Cmd(4, minimum=0, maximum=2, type=CHAR, access=Access.SEC)
        self.counter.setpoint_mode = Cmd(5, minimum=0, maximum=1, type=CHAR, access=Access.SEC)
        self.counter.new_setpoint = Cmd(6, minimum=0, maximum=32000, type=UINT, access=Access.SEC)
        self.counter.unit = Cmd(7, type=STRING)
        self.counter.mode = Cmd(8, minimum=0, maximum=2, type=CHAR, access=Access.SEC)
        # Controller subsystem, process 114
        self.controller = Subsystem(114, self)
        self.controller.valve_output = Cmd(1, minimum=0, maximum=100,
                                           rfunc=_valve_output_to_pct, wfunc=_pct_to_valve_output,
                                           type=ULONG, access=Access.SEC)
        self.controller.response_on_setpoint_change = Cmd(5, minimum=0, maximum=255, type=CHAR, access=Access.SEC)
        self.controller.response_when_stable = Cmd(17, minimum=0, maximum=255, type=CHAR, access=Access.SEC)
        self.controller.response_on_startup = Cmd(18, minimum=0, maximum=255, type=CHAR, access=Access.SEC)
        self.controller.PIDKp = Cmd(21, minimum=0.0, maximum=1e+10, type=FLOAT, access=Access.SEC)
        self.controller.PIDKi = Cmd(22, minimum=0.0, maximum=1e+10, type=FLOAT, access=Access.SEC)
        self.controller.PIDKd = Cmd(23, minimum=0.0, maximum=1e+10, type=FLOAT, access=Access.SEC)  ## double check
        #self.controller.TDS_up = Cmd(param=12, minimum=0.0, maximum=1e+10, type=FLOAT, access=Access.SEC)
        #self.controller.TDS_down = Cmd(param=11, minimum=0.0, maximum=1e+10, type=FLOAT, access=Access.SEC)
        #self.controller.smoothing = Cmd(process=117, param=4, minimum=0.0, maximum=1.0, type=FLOAT, access=Access.SEC)
        #self.controller.smoothing_rate = Cmd(process=117, param=5, minimum=0.0, maximum=1.0,
        #                                     type=FLOAT, access=Access.SEC)

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
        super().__init__(socket)


class PC(Controller):

    """Instrument for pressure controllers."""

    def __init__(self, socket):
        super().__init__(socket)


class BronkhorstTest(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {
            # 3.10.1: set setpoint node 3 to 50%
            ":06030101213E80\r\n": ":0403000005\r\n",
            # 3.10.3: request setpoint node 3 (-> 50%)
            ":06030401210121\r\n": ":06030201213E80\r\n",
            # 3.10.5: request measure from node 3 (50%)
            ":06030401210120\r\n": ":06030201213E80\r\n",
            # 3.10.6: request counter value from node 3, process 104, float
            ":06030468416841\r\n": ":0803026841459cffae\r\n",
            # set alarm.max_limit to 10 (secured UINT)
            ":0C0301800A40E121000A000A52\r\n": ":040300000b\r\n",
            # set fluid to "WATER" (secured str)
            ":110301800A40817100574154455200000A52\r\n": ":040300000f\r\n",
            # req control mode (process 1, parameter 4, CHAR), ret 10
            ":06030401010104\r\n": ":05030201040A\r\n",
            # req valve output (process 114, parameter 1, ULONG), ret 93.75
            ":06030472417241\r\n": ":080302724100f00000\r\n",
            # req usertag (process 113, parameter 6, STRING), ret USER
            ":0703047161716600\r\n": ":0A03027166005553455200\r\n"
        }
        self.i = Controller(socket)

    def test_conversions(self):
        msg = ":06030101213E80\r\n"
        self.assertEqual(AsciiProtocol.toAscii(AsciiProtocol.toBytes(msg)), msg)

    # manual 917027, examples pp. 18-24
    def test_write_int_3_10_1(self):
        # send SP 50 % (node 3, process 1, param 1, int = 16000)
        self.i.setpoint.write(50, node=3)

    def test_write_sec_uint(self):
        self.i.alarm.max_limit.write(10, node=3)

    def test_write_sec_string(self):
        self.i.fluid.write("WATER", node=3)

    def test_read_char(self):
        self.assertEqual(self.i.control_mode.read(node=3), 10)

    def test_read_uint_3_10_3(self):
        # req SP (node 3, process 1, param 1, int)
        Reader.index = 1
        self.assertEqual(self.i.setpoint.read(node=3), 50.0)

    def test_read_uint_3_10_5(self):
        # req MEASURE (node 3, process 1, int)
        Reader.index = 1
        self.assertEqual(self.i.measure.read(node=3), 50.0)

    def test_read_float_3_10_6(self):
        # req CNTRVALUE (node 3, process 104, float)
        self.assertAlmostEqual(self.i.counter.value.read(node=3), 5023.96, 2)

    def test_read_ulong(self):
        self.assertAlmostEqual(self.i.controller.valve_output.read(node=3),
                               93.75, 2)

    def test_read_string(self):
        self.assertEqual(self.i.identification.usertag.read(node=3), "USER")


if __name__ == "__main__":
    unittest.main()

