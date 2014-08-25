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


def _phys_channel(context):
    """Comedi uses device names such as /dev/comedi0 SUBDEVICE CHANNEL
    where SUBDEVICE and CHANNEL are integers.

    In the config file, we must set /dev/comedi0 as the port and
    SUBDEVICE.CHANNEL as the node.

    .. code-block:: yaml

        daq:
            /dev/comedi0:
                - node: 1.1
                  name: dio1
                - node: 1.2
                  name: dio2

    """
    filename = context.path[0].device
    subdevice, channel = context.node.split(".")
    device = c.comedi_open(filename)
    if not device:
        raise ComediError("Failed to open device %s" % filename)
    return device, int(subdevice), int(channel)


class DioProtocol(drv.Protocol):

    """Protocol for Digital IO lines."""

    def read(self, context):
        device, subdevice, channel = _phys_channel(context)
        c.comedi_dio_config(device, subdevice, channel, c.COMEDI_OUTPUT)
        chk, value = c.comedi_dio_read()
        if chk < 0:
            raise ComediError("Failed to read on %s" % context.node)
        return value

    def write(self, context):
        device, subdevice, channel = _phys_channel(context)
        chk = c.comedi_dio_config(device, subdevice, channel, c.COMEDI_OUTPUT)
        if chk < 0:
            raise ComediError("Failed to write on %s" % context.node)


class AioProtocol(drv.Protocol):

    """Protocol for Analog Input and Analog Output lines."""

    def read(self, context):
        device, subdevice, channel = _phys_channel(context)
        chk, value = c.comedi_data_read(device, subdevice, channel,
                                        0, 0)  # range, aref
        if chk < 0:
            raise ComediError("Failed to read on %s" % context.node)
        return value

    def write(self, context):
        device, subdevice, channel = _phys_channel(context)
        chk = c.comedi_data_write(device, subdevice, channel,
                                  0, 0, context.value)
        if chk < 0:
            raise ComediError("Failed to write on %s" % context.node)


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
