"""IEEE 488.1 standard.

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access


class IeeeCommunicationProtocol(drv.CommunicationProtocol):

    """Communication protocol for the IEEE 488.1 standard."""

    def read(self, context):
        self._socket.write("*{cmd}?\n".format(cmd=context.reader))
        return self._socket.readline().strip()

    def write(self, context):
        if context.value is not None:
            msg = "*{cmd} {val}\n".format(cmd=context.writer,
                                          val=context.value)
        else:
            msg = "*{cmd}\n".format(cmd=context.writer)
        self._socket.write(msg)


def _bool(x): return bool(int(x))


class Ieee488_1Subsystem(drv.Subsystem):
    """IEEE 488.1 Requirements in IEEE 488.2 standard.

    Section 4.1

    """
    def __init__(self, socket, parent=None):
        super(Ieee488_1Subsystem, self).__init__()
        self.setProtocol(IeeeCommunicationProtocol(socket, parent))

        self.source_handshake = Cmd("SH1")
        self.acceptor_handshake = Cmd("AH1")
        self.request_service = Cmd("SR1", access=Access.WO)
        self.listener3 = Cmd("L3")
        self.listener4 = Cmd("L4")
        self.listenerE3 = Cmd("LE3")
        self.listenerE4 = Cmd("LE4")
        self.talker5 = Cmd("T5")
        self.talker6 = Cmd("T6")
        self.talkerE5 = Cmd("TE5")
        self.talkerE6 = Cmd("TE6")
        self.parallel_poll = Cmd("PP0", minimum=0, maximum=1,
                                 wfunc=int, rfunc=_bool)

        self.clear_device = Cmd("DC1", access=Access.WO)
        self.trigger_device = Cmd("DT0", minimum=0, maximum=1,
                                  wfunc=int, rfunc=_bool,
                                  access=Access.WO)
        self.electrical_interface = Cmd("E1", minimum=1, maximum=2, rfunc=int)


class TestIeee488_1(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        socket.msg = {"*PP0?\n": "0",
                      "*PP0 1\n": "",
                      "*DC1\n": "",}
        self.i = Ieee488_1Subsystem(socket)

    def test_read(self):
        self.assertFalse(self.i.parallel_poll.read())

    def test_write(self):
        self.i.parallel_poll.write(True)

    def test_write_write_only(self):
        self.i.clear_device.write()

    def test_missing_value(self):
        self.assertRaises(drv.DriverError, self.i.parallel_poll.write)


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logging.getLogger("pyhard2").setLevel(logging.DEBUG)
    unittest.main()
