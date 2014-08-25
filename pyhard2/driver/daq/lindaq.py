"""Comedi wrappers to communicate with DAQ hardware on linux.

Warning:

    The linux driver is not tested.

"""
import pyhard2.driver as drv
import comedi as c


subdevice_type_name = """
    unused ai ao di do dio counter timer memory calib proc serial pwm
    """.split()
assert(len(subdevice_type_name) == 13)

comedi_subdevice_type = dict(zip(subdevice_type_name, range(13)))


class ComediError(drv.HardwareError): pass


def _parse_name(device_name):
    # write device_name like FILENAME.SUBDEVICE.CHANNEL
    # e.g.: /dev/comedi0.1.2
    filename, subdevice, channel = device_name.split(".")
    device = c.comedi_open(filename)
    if not device:
        raise ComediError("Failed to open device %s" % filename)
    return device, int(subdevice), int(channel)


class DioProtocol(drv.Protocol):

    """Protocol for Digital IO lines."""

    def read(self, context):
        device, subdevice, channel = _parse_name(context.reader)
        c.comedi_dio_config(device, subdevice, channel, c.COMEDI_OUTPUT)
        chk, value = c.comedi_dio_read()
        if chk < 0:
            raise ComediError("Failed to read on %s" % context.reader)
        return value

    def write(self, context):
        device, subdevice, channel = _parse_name(context.writer)
        chk = c.comedi_dio_config(device, subdevice, channel, c.COMEDI_OUTPUT)
        if chk < 0:
            raise ComediError("Failed to write on %s" % context.writer)


class AioProtocol(drv.Protocol):

    """Protocol for Analog Input and Analog Output lines."""

    def read(self, context):
        device, subdevice, channel = _parse_name(context.reader)
        chk, value = c.comedi_data_read(device, subdevice, channel,
                                        0, 0)  # range, aref
        if chk < 0:
            raise ComediError("Failed to read on %s" % context.reader)
        return value

    def write(self, context):
        device, subdevice, channel = _parse_name(context.writer)
        chk = c.comedi_data_write(device, subdevice, channel,
                                  0, 0, context.value)
        if chk < 0:
            raise ComediError("Failed to write on %s" % context.writer)


def get_dio_channels(path):
    device = c.comedi_open(path)
    n_subdevices = c.comedi_get_n_subdevices(device)
    dio_list = []
    for n_subdevice in range(n_subdevices):
        if (c.comedi_get_subdevice_type(device, n_subdevice)
            == comedi_subdevice_type("dio")):
            n_channel = c.comedi_get_n_channels(device, n_subdevice)
            #dio_list.extend([DioSocket(path, n_subdevice, chan)
            #                for chan in range(n_channel)])
    return dio_list
