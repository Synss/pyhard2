import comedi as c


subdevice_type_name = """
    unused ai ao di do dio counter timer memory calib proc serial pwm
    """.split()
assert(len(subdevice_type_name) == 13)

comedi_subdevice_type = dict(zip(subdevice_type_name, range(13)))


class ComediError(IOError):
    pass


class ComediSocket(object):

    subsytem_type = "unused"

    def __init__(self, filename, subdevice, channel):
        self.filename = filename
        self.device = c.comedi_open(filename)
        self.subdevice = subdevice
        self.channel = channel
        if not self.device:
            raise ComediError("Failed to open device %s" % filename)
        #val = c.comedi_get_subdevice_type(self.device, self.subdevice)
        #if not val is self.subsytem_type:
        #    raise ComediError("Subdevice %i on %s is not a digital IO device"
        #                      % (subdevice, filename))
        c.comedi_dio_config(self.device, self.subdevice, self.channel,
                            c.COMEDI_OUTPUT)

    def __repr__(self):
        return "%s(%r, %r, %r)" % (self.__class__.__name__,
                                   self.filename, self.subdevice, self.channel)


class DioSocket(ComediSocket):

    subsytem_type = "dio"

    def __init__(self, filename, subdevice, channel):
        super(DioSocket, self).__init__(filename, subdevice, channel)
        c.comedi_dio_config(self.device, self.subdevice, self.channel,
                            c.COMEDI_OUTPUT)

    def read(self):
        chk, val = c.comedi_dio_read(self.device, self.subdevice, self.channel)
        return val

    def write(self, state):
        c.comedi_dio_write(self.device, self.subdevice, self.channel, state)


class AiSocket(ComediSocket):

    subdevice_type = "ai"

    def __init__(self, filename, subdevice, channel):
        super(AiSocket, self).__init__(filename, subdevice, channel)

    def read(self):
        chk, val = c.comedi_read(self.device, self.subdevice, self.channel,
                                 0, 0)  # range, aref
        return val

    def write(self, x):
        raise NotImplementedError


class AoSocket(ComediSocket):

    subdevice_type = "ao"

    def __init__(self, filename, subdevice, channel):
        super(AoSocket, self).__init__(filename, subdevice, channel)

    def read(self):
        raise NotImplementedError
    
    def write(self, data):
        chk = c.comedi_write(self.device, self.subdevice, self.channel,
                             0, 0, data)


def get_dio_channels(path):
    device = c.comedi_open(path)
    n_subdevices = c.comedi_get_n_subdevices(device)
    dio_list = []
    for n_subdevice in range(n_subdevices):
        if (c.comedi_get_subdevice_type(device, n_subdevice)
            == comedi_subdevice_type("dio")):
            n_channel = c.comedi_get_n_channels(device, n_subdevice)
            dio_list.extend([DioSocket(path, n_subdevice, chan)
                            for chan in range(n_channel)])
    return dio_list
