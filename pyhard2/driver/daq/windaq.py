import numpy as np

# http://code.google.com/p/pylibnidaqmx
from nidaqmx import DigitalOutputTask, DigitalInputTask
from nidaqmx import AnalogInputTask, AnalogOutputTask


class DioTask(DigitalOutputTask, DigitalInputTask):

    channel_type = "DO"

    def __init__(self, name=""):
        super(DioTask, self).__init__(name)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - Tasks/Sockets

class AiSocket(AnalogInputTask):

    def __init__(self, phys_channel, name="", terminal="default",
                 min_val=-10, max_val=10, units="volts",
                 custom_scale_name=None):
        super(AiSocket, self).__init__(name)  # FIXME ch name / task name?
        self.create_voltage_channel(phys_channel, name, terminal,
                                    min_val, max_val, units, custom_scale_name)

    def read(self, n=100):
        data = np.average(AnalogInputTask.read(self, n))
        return data

    def write(self, x):
        raise NotImplementedError


class AoSocket(AnalogOutputTask):

    def __init__(self, phys_channel, name="",
                 min_val=-10, max_val=10, units="volts",
                 custom_scale_name=None):
        super(AoSocket, self).__init__(name)  # FIXME
        self.create_voltage_channel(phys_channel, name,
                                    min_val, max_val, units, custom_scale_name)

    def read(self):
        raise NotImplementedError

    def write(self, x):
        AnalogOutputTask.write(self, x)


class DioSocket(DioTask):

    def __init__(self, lines, name="", grouping="per_line"):
        super(DioSocket, self).__init__()
        self.create_channel(lines, name, grouping)

    def read(self):
        return DioTask.read(self, 1)[0].item()

    def write(self, state):
        DioTask.write(self, state if not hasattr(state, "tolist")
                                  else state.tolist()[0])  # numpy compatibility

