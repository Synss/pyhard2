"""FLOW-BUS protocol for Bronkhorst instruments.


The protocol is described in the instruction manual number 9.17.027.
The implementation uses the `Construct library <http://construct.readthedocs.org/en/latest/>`__.

"""
from binascii import unhexlify
import unittest
from construct import *


header = Struct("header",
    Byte("length"),
    Byte("node")
)

command = Enum(Byte("command"),
    status = 0,
    write = 1,  #           <--
    write_no_status = 2,
    write_with_source = 3,
    read = 4,  #            <--
    send_repeat = 5,
    stop_process = 6,
    start_process = 7,
    claim_process = 8,
    unclaim_process = 9
)


def Data(label):
    return Struct(label,
    BitStruct("process",
        Flag("chained"),
        BitField("number", 7)),
    BitStruct("parameter",
        Const(Flag("chained"), False),
        Enum(BitField("type", 2),
             c = 0x00 >> 5,  # 0
             i = 0x20 >> 5,  # 1
             f = 0x40 >> 5,  # 2
             l = 0x40 >> 5,  # 2
             s = 0x60 >> 5), # 3
        BitField("number", 5)),
    )

read_command = Struct("request",
    Embed(header),
    OneOf(command, ['read']),
    Data("index"),
    Data("data"),
    If(lambda ctx: ctx.data.parameter.type == "s",
        Const(UBInt8("string_length"), 0)),
    Terminator
)

def write_command(type_, secured):
    return Struct("send",
    Embed(header),
    OneOf(command, ['write', 'write_no_status']),
    Const(String(None, 3), "\x80\x0a\x40") if secured else Pass,
    Data("index"),
    dict(
        c=UBInt8("value"),
        i=UBInt16("value"),
        f=BFloat32("value"),
        l=UBInt32("value"),
        s=Embed(Struct(None, UBInt8("string_length"),
            IfThenElse("value",
            lambda ctx: ctx["string_length"] is 0,
            CString(None),
            # read string_length bytes (PascalString)
            MetaField(None, lambda ctx: ctx["string_length"]))))
    )[type_],
    Const(String(None, 3), "\x00\x0a\x52") if secured else Pass,
    Terminator
)

error_message = Struct("FLOW-BUS error",
    Embed(header),
    Enum(Byte("error"),
        colon_missing = 1,
        first_byte = 2,
        message_length = 3,
        receiver = 4,
        communication_error = 5,
        sender_timeout = 8,
        answer_timeout = 9,
    )
)

status_message = Struct("FLOW-BUS status",
    Embed(header),
    command,
    Enum(Byte("status"),
        no_error = 0x00,
        process_claimed = 0x01,
        command_error = 0x02,
        process_error = 0x03,
        parameter_error = 0x04,
        param_type_error = 0x05,
        param_value_error = 0x06,
        network_not_active = 0x07,
        timeout_start_char = 0x08,
        timeout_serial_line = 0x09,
        hardware_mem_error = 0x0a,
        node_number_error = 0x0b,
        general_com_error = 0x0c,
        read_only_param = 0x0d,
        PC_com_error = 0x0e,
        no_RS232_connection = 0x0f,
        PC_out_of_mem = 0x10,
        write_only_param = 0x11,
        syst_config_unknown = 0x12,
        no_free_node_address = 0x13,
        wrong_iface_type = 0x14,
        serial_port_error = 0x15,
        serial_open_error = 0x16,
        com_error = 0x17,
        iface_busmaster_error = 0x18,
        timeout_ans = 0x19,
        no_start_char = 0x1a,
        first_digit_error = 0x1b,
        host_buffer_overflow = 0x1c,
        buffer_overflow = 0x1d,
        no_answer_found = 0x1e,
        error_closing_connection = 0x1f,
        synch_error = 0x20,
        send_error = 0x21,
        com_error_2 = 0x22,
        module_buffer_overflow = 0x23
    ),
    Byte("byte_index"),
    Terminator
)


class _Data(object):

    class Byte(object):

        def __init__(self, number, type="c", chained=False):
            self.number = number
            self.type = type
            self.chained = chained

    def __init__(self, process, param, param_type, chained=False):
        self.process = _Data.Byte(process, chained=chained)
        self.parameter = _Data.Byte(param, param_type)


class Reader(object):

    index = 1

    def __init__(self, node, process, param, param_type):
        self.length = 0
        self.node = node
        self.command = "read"
        self.index = _Data(process, Reader.index, param_type)
        self.data = _Data(process, param, param_type)
        self.string_length = 0
        self.length = len(self.build()) - 1

    @classmethod
    def fromContext(cls, context):
        process = context.subsystem.process
        return cls(context.node, process, context.reader,
                   context._command.type)

    def build(self):
        """object to message"""
        return read_command.build(self)

    @staticmethod
    def parse(msg):
        """message to object"""
        return read_command.parse(msg)


class Writer(object):

    def __init__(self, node, process, param, param_type, secured, value):
        self.length = 0
        self.node = node
        self.command = "write"
        self.index = _Data(process, param, param_type, secured)
        self.param_type = param_type
        self.secured = secured
        self.value = value
        self.string_length = 0
        self.length = len(self.build()) - 1

    @classmethod
    def fromContext(cls, context):
        process = context.subsystem.process
        return cls(context.node, process, context.writer,
                   context._command.type, context._command.access ==
                   "Access.SEC", context.value)

    def build(self):
        """object to message"""
        return write_command(self.param_type, self.secured).build(self)

    @staticmethod
    def parse(msg, type_, secured=False):
        """message to object"""
        return write_command(type_, secured).parse(msg)


class Status(object):

    @staticmethod
    def parse(msg):
        return status_message.parse(msg).status


class TestFlowBus(unittest.TestCase):

    def setUp(self):
        self.msg = dict(status=unhexlify("0403000005"),
                        read=unhexlify("06030401210121"),
                        write=unhexlify("06030101213E80"),
                        secwrite=unhexlify("0C0301800A40E121000A000A52"))

    def test_data_builder(self):
        self.assertEqual(Data("").build(_Data(10, 2, "i")), unhexlify("0a22"))

    def test_reader_builder(self):
        self.assertEqual(read_command.build(Reader(3, 1, 1, "c")),
                         unhexlify("06030401010101"))

    def test_writer_builder(self):
        self.assertEqual(
            write_command("c", False).build(Writer(3, 1, 2, "c", False, 10)),
            unhexlify("05030101020a"))

    def test_status(self):
        msg = self.msg["status"]
        self.assertEqual(status_message.parse(msg).command, "status")

    def test_status_build(self):
        msg = self.msg["status"]
        self.assertEqual(status_message.build(status_message.parse(msg)), msg)

    def test_read(self):
        msg = self.msg["read"]
        self.assertEqual(read_command.parse(msg).command, "read")

    def test_read_build(self):
        msg = self.msg["read"]
        self.assertEqual(read_command.build(read_command.parse(msg)), msg)

    def test_write(self):
        msg = self.msg["write"]
        self.assertEqual(write_command("i", False).parse(msg).command, "write")

    def test_write_build(self):
        msg = self.msg["write"]
        self.assertEqual(
            write_command("i", False).build(write_command("i", False).parse(msg)),
            msg)

    def test_sec_write(self):
        msg = self.msg["secwrite"]
        self.assertEqual(
            write_command("i", True).build(write_command("i", True).parse(msg)),
            msg)

