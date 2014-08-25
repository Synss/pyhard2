"""pylibnidaqmx wrappers to communicate with DAQ hardware on Windows.

"""
import numpy as np
import logging
logging.basicConfig()
logger = logging.getLogger("pyhard2")
import pyhard2.driver as drv

try:
    # http://code.google.com/p/pylibnidaqmx
    from nidaqmx import DigitalOutputTask, DigitalInputTask
    from nidaqmx import AnalogInputTask, AnalogOutputTask
except ImportError:
    logger.critical(
        "The pylibnidaqmx library failed to load.  DAQ driver unavailable.")

    class __Dummy(object):

        """We silence the ImportError to generate the documentation."""

        def __init__(self):
            raise NotImplementedError

    class __InputTask(__Dummy): pass

    class __OutputTask(__Dummy): pass

    AnalogInputTask = DigitalInputTask = __InputTask
    AnalogOutputTask = DigitalOutputTask = __OutputTask

class DioProtocol(drv.Protocol):

    """Protocol for Digital IO lines."""

    def read(self, context):
        task = DigitalInputTask()
        task.create_channel(context.reader)  # phys_channel
        return np.average(task.read()).item()  # XXX

    def write(self, context):
        task = DigitalOutputTask()
        task.create_channel(context.writer)
        task.write(context.value)


class AioProtocol(drv.Protocol):

    """Protocol for Analog Input and Analog Output lines."""

    def read(self, context):
        task = AnalogInputTask()
        minimum, maximum = context.minimum, context.maximum
        if not minimum:
            minimum = -10
        if not maximum:
            maximum = 10
        task.create_voltage_channel(context.reader,  # phys channel
                                    min_val=minimum,
                                    max_val=maximum)
        return np.average(task.read(100)).item()

    def write(self, context):
        task = AnalogOutputTask()
        minimum, maximum = context.minimum, context.maximum
        if not minimum:
            minimum = -10
        if not maximum:
            maximum = 10
        task.create_voltage_channel(context.writer,  # phys channel
                                    min_val=minimum,
                                    max_val=maximum)
        task.write(self, context.value)

