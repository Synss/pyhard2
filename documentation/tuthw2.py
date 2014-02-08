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
    print(multimeter.measure)
    print(multimeter.unit)


if __name__ == "__main__":
    import sys
    main(sys.argv[1])

