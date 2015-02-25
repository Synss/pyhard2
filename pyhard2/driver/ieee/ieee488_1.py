"""IEEE 488.1 standard.

"""
import unittest
import pyhard2.driver as drv
import pyhard2.driver.ieee as ieee
Cmd, Access = drv.Command, drv.Access



def _bool(x): return bool(int(x))


class Ieee4881(drv.Subsystem):
    """IEEE 488.1 Requirements in IEEE 488.2 standard.

    Section 4.1

    """
    def __init__(self, socket, parent=None):
        super(Ieee4881, self).__init__(parent)
        self.setProtocol(ieee.Ieee488CommunicationProtocol(socket, parent))

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
        self.i = Ieee4881(socket)

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
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    unittest.main()
