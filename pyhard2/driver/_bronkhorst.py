'''
FLOW-BUS
'''

from construct import *


def byte2hex(bstr):
    return "".join("%02X" % ord(x) for x in bstr)

def hex2byte(hstr):
    return "".join(chr(int(hstr[i:i+2], 16)) for i in range(0, len(hstr), 2))


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


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Simple unit tests in main
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

if __name__ == '__main__':
    ''' Manual 917027, examples pp. 18-24 '''
    # send SP (node 3, process 1, param 1, int = 16000)
    write_command.parse(':\x06\x03\x01\x01\x21\x3e\x80\r\n')
    # answer (status)
    status_message.parse(':\x04\x03\x00\x00\x05\r\n')  # was node 1 in manual

    write_command.parse(''.join((':',
                '\x1d\x03\x01',
                '\x80',                     # process 1
                '\x0a\x40',                 # param   1.1
                '\x81',                     # process 2
                '\xc5\x00\x00\x00\x00',     # param   2.1
                '\xc6\x3f\x80\x00\x00',     # param   2.2
                '\xc7\x00\x00\x00\x00',     # param   2.3
                '\x48\x00\x00\x00\x00',     # param   2.4 <- chained in manual
                '\x00',                     # process 3
                '\x0a\x52',                 # param   3.1
                '\r\n')))
    # answer
    status_message.parse(':\x04\x03\x00\x00\x1c\r\n')

    # req SP (node 3, process 1, param 1, int)
    read_command.parse(':\x06\x03\x04\x01\x21\x01\x21\r\n')
    # ans (1600)
    write_command.parse(':\x06\x03\x02\x01\x21\x3e\x80\r\n')

    # req chain
    #query_param.parse(':\x1a\x03\x04\xf1\xec\xf1\x63\x14\r\n')
    #^^^ para.chained = process.chained = False?
    read_command.parse(''.join((':',
            '\x1a\x03\x04\xf1\xec\x71\x63\x14\x6d\x71\x66\x00',
            '\x01\xae\x01\x20\xcf\x01\x4d\xf0\x01\x7f\x07\x71',
            '\x01\x71\x0a\r\n')))   # <-- original
    # ans
    write_command.parse(''.join((':',
            '\x41\x03\x02',
            '\xf1',                                     # process 1
            '\xec\x14'                                  # param   1.1
            '\x4d\x36\x32\x31\x32\x33\x34\x35\x41\x20', # value   1.1
            '\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20',
            '\x6d\x00',                                 # param   1.2
            '\x55\x53\x45\x52\x54\x41\x47\x00',         # value   1.2
            '\x01',                                     # process 2
            '\xae',                                     # param   2.1
            '\x1c\xd8',                                 # value   2.1
            '\xcf',                                     # param   2.2
            '\x3f\x80\x00\x00',                         # value   2.2
            '\xf0\x07',                                 # param   2.3
            '\x6d\x6c\x6e\x2f\x6d\x69\x6e',             # value   2.3
            '\x71\x0a',                                 # param   2.4
            '\x4e\x32\x20\x20\x20\x20\x20\x20\x20\x20', # value   2.4
            '\r\n')))

    # req meas (node 3, process 1, int)
    read_command.parse(':\x06\x03\x04\x01\x21\x01\x20\r\n')
    # ans (1600)
    write_command.parse(':\x06\x03\x02\x01\x21\x3e\x80\r\n')

    # req counter val (node 3, process 104, float)
    read_command.parse(':\x06\x03\x04\x68\x41\x68\x41\r\n')
    # ans 5023.96
    write_command.parse(':\x08\x03\x02\x68\x41\x45\x9c\xff\xae\r\n')

