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


def _phys_channel(context):
    return "/".join((context.path[0].device,
                     context.node))


def _task_name(context):
    return context.node.replace("/", "_")


class DioTask(DigitalOutputTask, DigitalInputTask):

    """A class that inherits from both `DigitalInputTask` and
    `DigitalOutputTask`.

    Without the double inheritance provided here, `DigitalInputTask.read()`
    switches the state off.

    """
    def __init__(self, name=""):
        super(DioTask, self).__init__(name)


class DioProtocol(drv.Protocol):

    """Protocol for Digital IO lines."""

    def read(self, context):
        task = DioTask(_task_name(context))
        task.create_channel(_phys_channel(context), grouping="per_line")
        raw = task.read(1)
        return raw[0].item()

    def write(self, context):
        task = DioTask(_task_name(context))
        task.create_channel(_phys_channel(context), grouping="per_line")
        task.write(context.value)


class VoltageAioProtocol(drv.Protocol):

    """Protocol for Analog Input and Analog Output lines."""

    def read(self, context):
        task = AnalogInputTask(_task_name(context))
        minimum = context.minimum if context.minimum is not None else -10
        maximum = context.maximum if context.maximum is not None else 10
        task.create_voltage_channel(_phys_channel(context),
                                    terminal="rse",
                                    min_val=minimum,
                                    max_val=maximum)
        task.start()
        raw = task.read(100)
        task.stop()
        return np.average(raw).item()

    def write(self, context):
        task = AnalogOutputTask(_task_name(context))
        minimum = context.minimum if context.minimum is not None else -10
        maximum = context.maximum if context.maximum is not None else 10
        task.create_voltage_channel(_phys_channel(context),
                                    terminal="rse",
                                    min_val=minimum,
                                    max_val=maximum)
        task.write(self, context.value, auto_start=False)
        task.start()

