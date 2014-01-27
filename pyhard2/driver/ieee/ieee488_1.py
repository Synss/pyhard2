import pyhard2.driver as drv
Param, Action = drv.Parameter, drv.Action


__all__ = ["Ieee488_1", "Mandatory"]


class IeeeProtocol(drv.SerialProtocol):

    def __init__(self):
        super(IeeeProtocol, self).__init__(
            fmt_read="*{param[getcmd]}?\n",
            fmt_write="*{param[setcmd]} {val}\n",
        )


class Mandatory(drv.Subsystem):
    """
    IEEE 488.1 Requirements in IEEE 488.2 standard.

    Section 4.1
    """

    def __init__(self, instrument):
        super(Mandatory, self).__init__(instrument)

    source_handshake = Param("SH1", doc="Source handshake")
    acceptor_handshake = Param("AH1", doc="Acceptor handshake")
    request_service = Action("SR1", doc="Service request")
    talker5 = Param("T5", doc="Talker")  # 5 or 6 or TE5, TE6
    talker6 = Param("T6", doc="Talker")
    listener3 = Param("L3", doc="Listener")  # 3 or 4 or LE3, LE4
    listener4 = Param("L4", doc="Listener")
    parallel_poll = Param("PP0", doc="Parallel poll")  # 0 or 1
    clear_device = Action("DC1", doc="Device clear")
    trigger_device = Action("DT0", doc="Device trigger")  # 0 or 1
    #controller
    electrical_interface = Param("E1", doc="Electrical interface")  # 1 or 2


class Ieee488_1(drv.Instrument):

    def __init__(self, socket):
        socket.newline = "\n"
        super(Ieee488_1, self).__init__(socket, IeeeProtocol())
        self.mandatory = Mandatory(self)
        self.default = "mandatory"

