import pyhard2.driver as drv


def parse_response(which="measure"):
    def parser(response):
        split_response = response.split()          # ["QM,+0023.0", "Deg", "C"]
        echo, value = split_response[0].split(",") # "QM", "+0023.0"
        unit = " ".join(split_response[1:])        # "Deg C"
        return float(value) if which == "measure" else unit
    return parser


class FlukeProtocol(drv.SerialProtocol):

    def __init__(self, socket, async=False):
        super(FlukeProtocol, self).__init__(socket, async,
                                            fmt_read="{param[getcmd]}\r")

    def _encode_read(self, subsys, param):
        ack = super(FlukeProtocol, self)._encode_read(subsys, param)
        assert(ack == "0")
        return self.socket.readline().strip()


class FlukeSubsystem(drv.Subsystem):

    def __init__(self, protocol):
        super(FlukeSubsystem, self).__init__(protocol)
        for name, code in dict(blue=10,
                               hold=11,
                               min_max=12,
                               rel=13,
                               up_arrow=14,
                               shift=15,
                               Hz=16,
                               range=17,
                               down_arrow=18,
                               backlight=19,
                               calibration=20,
                               auto_hold=21,
                               fast_min_max=22,
                               logging=23,
                               cancel=27,
                               wake_up=28,
                               setup=29,
                               save=30).iteritems():
            self.add_action_by_name("press_button_%s" % name, "SF %i" % code)

    measure = drv.Parameter("QM", getter_func=parse_response())
    unit = drv.Parameter("QM", getter_func=parse_response("unit"))


class Fluke18x(drv.Instrument):

    def __init__(self, socket, async=False):
        super(Fluke18x, self).__init__(socket, async)
        socket.timeout = 1.0
        socket.newline = "\r"
        protocol = FlukeProtocol(socket, async)
        self.main = FlukeSubsystem(protocol)


def main(serial_port):
    socket = drv.Serial(serial_port)
    multimeter = Fluke18x(socket)
    print(multimeter)


if __name__ == "__main__":
    import sys
    main(sys.argv[1])


