"""pylibnidaqmx wrappers to communicate with DAQ hardware on Windows.

"""
import numpy as np

# http://code.google.com/p/pylibnidaqmx
from nidaqmx import DigitalOutputTask, DigitalInputTask
from nidaqmx import AnalogInputTask, AnalogOutputTask

import pyhard2.driver as drv

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

