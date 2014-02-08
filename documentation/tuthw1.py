import pyhard2.driver as drv


def parse_response(which="measure"):
    def parser(response):
        split_response = response.split()          # ["QM,+0023.0", "Deg", "C"]
        echo, value = split_response[0].split(",") # "QM", "+0023.0"
        unit = " ".join(split_response[1:])        # "Deg C"
        return float(value) if which == "measure" else unit
    return parser


class FlukeSubsystem(drv.Subsystem):

    def __get_measure(self):
        socket = self.protocol.socket
        socket.write("QM\r")      # "QM\r"
        ack = socket.readline()   # "0\r"
        assert(ack == "0\r")
        return socket.readline()  # "QM,+0023.0 Deg C"

    measure = drv.Parameter(__get_measure, getter_func=parse_response())
    unit = drv.Parameter(__get_measure, getter_func=parse_response("unit"))


class Fluke18x(drv.Instrument):

    def __init__(self, socket, async=False):
        super(Fluke18x, self).__init__(socket, async)
        socket.timeout = 1.0
        socket.timeout.newline = "\r"
        protocol = drv.ProtocolLess(socket, async)
        self.main = FlukeSubsystem(protocol)


def main(serial_port):
    socket = drv.Serial(serial_port)
    with Fluke18x(socket) as multimeter:
        print(multimeter)
        print(multimeter.measure)
        print(multimeter.unit)


if __name__ == "__main__":
    import sys
    main(sys.argv[1])

