'''
FLOW-BUS
'''

from construct import *


def byte2hex(bstr):
    return "".join("%02X" % ord(x) for x in bstr)

def hex2byte(hstr):
    return "".join(chr(int(hstr[i:i+2], 16)) for i in range(0, len(hstr), 2))

def long2float(value):
    return BFloat32("").parse(UBInt32("").build(value))

def float2long(value):
    return UBInt32("").parse(BFloat32("").build(value))


class ByteHex(object):

    def __init__(self, c):
        self.__construct = c

    def _convert(self, msg, fun):
        return "".join((msg[0], fun(msg[1:-2]), msg[-2:]))

    def build(self, msg):
        return self._convert(
            self.__construct.build(msg), byte2hex)

    def parse(self, msg):
        return self.__construct.parse(self._convert(msg, hex2byte))


header = Struct("FLOW-BUS packet header",
    Const(Bytes(None, 1), ':'),  # '\x3a'
    Byte("length"),
    Byte("node")
)


end = Struct("FLOW-BUS packet end",
    Const(Bytes(None, 2), '\r\n'),  # '\x0d\x0a'
    Terminator
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


process = BitStruct("process",
    Flag("chained"),
    BitField("number", 7)
)


param_type = Enum(BitField("type", 2),
    c = 0x00 >> 5,  # 0
    i = 0x20 >> 5,  # 1
    f = 0x40 >> 5,  # 2
    l = 0x40 >> 5,  # 2
    s = 0x60 >> 5   # 3
)


param = BitStruct("param",
    Flag("chained"),
    param_type,
    BitField("number", 5)
)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# This section has the interesting stuff
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


_write_command = Struct("FLOW-BUS send",
    Embed(header),
    OneOf(command, ['write', 'write_no_status']),  # 04
    RepeatUntil(lambda obj, ctx:
                not obj.chained, Struct("process_list",
            Embed(process),
            RepeatUntil(lambda obj, ctx:
                        not obj.chained, Struct("param_list",
                    Embed(param),
                    Embed(Switch(None, lambda ctx: ctx.type,
                    {
                        "c": Struct(None, UBInt8("value")),
                        "i": Struct(None, UBInt16("value")),
                        "f": Struct(None, BFloat32("value")),
                        "l": Struct(None, UBInt32("value")),
                        "s": Struct(None, UBInt8("string_length"),
                            IfThenElse("value",
                                lambda ctx: ctx["string_length"] is 0,
                                CString(None),
                                # read string_length bytes (PascalString)
                                MetaField(None, lambda ctx: ctx["string_length"])
                            ))
                    }
                    )),
                ),
            ),
        ),
    ),
    Embed(end)
)


write_command = ByteHex(_write_command)


def extract_values(wr_cmd):
    for process in write_command.parse(wr_cmd).process_list:
        for param in process.param_list:
            yield process.number, param.number, param.value



_read_command = Struct("FLOW-BUS query",
    Embed(header),
    OneOf(command, ['read']),  # 01
    RepeatUntil(lambda obj, ctx:
                not obj.chained, Struct("process_list",
        Embed(process),
        RepeatUntil(lambda obj, ctx:
                    not obj.idx.chained, Struct("param_list",
            Rename("idx", param),
            process,
            Embed(param),
            If(lambda ctx: ctx.type == "s",
               Optional(Byte("string_length"))
            ),
        )),
    )),
    Embed(end)
)


read_command = ByteHex(_read_command)


_error_message = Struct("FLOW-BUS error",
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


error_message = ByteHex(_error_message)


_status_message = Struct("FLOW-BUS status",
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
    Embed(end)
)


status_message = ByteHex(_status_message)

