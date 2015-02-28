"""IEEE 488.2 standard.

"""
import unittest
import pyhard2.driver as drv
Cmd, Access = drv.Command, drv.Access
import pyhard2.driver.ieee as ieee


def _parse_idn(msg):
    """returns (manufacturer, model, serial_number, firmware level)"""
    return tuple(idn.strip() for idn in msg.split(","))

def _self_test(msg):
    if msg is not "0":
        raise ieee.HardwareError("Self test failed.")


class Ieee4882(drv.Subsystem):
    """IEEE 488.2 Requirements.

    - Table 4-4 -- Required Status Reporting Common Commands
    - Table 4-7 -- Required Internal Operation Common Commands
    - Table 4-17 -- Required Synchronization Commands

    """
    def __init__(self, socket, parent=None):
        super().__init__(parent)
        self.setProtocol(ieee.Ieee488CommunicationProtocol(socket, parent))
        # Table 10-2
        # System data
        self.identification = Cmd('IDN', access=Access.RO,
                                  rfunc=_parse_idn,
                                  doc="Identification query")
        # Internal operations
        self.reset = Cmd("RST", access=Access.WO)
        self.self_test = Cmd("TST", access=Access.RO, rfunc=_self_test)
        # Status & Event
        self.clear_status = Cmd("CLS", access=Access.WO)
        self.service_request_enable = Cmd("SRE", minimum=0, maximum=255)  # 11.3.2
        self.event_status_enable = Cmd("ESE")  # 11.4.2.3
        self.event_status_register = Cmd("ESR", access=Access.RO)  # 11.5.1.2
        self.status_byte = Cmd('STB', access=Access.RO)
        # Synch
        self.wait_to_continue = Cmd("WAI", access=Access.WO)  # 12.5.1
        self.operation_completed = Cmd("OPC")  # 12.5.3


class PowerOn(drv.Subsystem):
    """Table 4-5 -- Optional Power-On Common Commands"""
    def __init__(self, parent):
        super().__init__(parent)
        self.status = Cmd("PSC", access=Access.RO)
        self.clear_status = Cmd("PSC", access=Access.WO)

class ParallelPoll(drv.Subsystem):
    """Table 4-6 -- Optional Parallel Poll Common Commands"""
    def __init__(self, parent):
        super().__init__(parent)
        self.individual_status = Cmd('IST', access=Access.RO)
        self.enable_register = Cmd('PRE')

class ResourceDescription(drv.Subsystem):
    """Table 4-8 -- Optional Resource Description Common Command"""
    def __init__(self, parent):
        super().__init__(parent)
        self.transfer = Cmd('RDT')

class ProtectedUserData(drv.Subsystem):
    """Table 4-9 -- Optional Protected User Data Command"""
    def __init__(self, parent):
        super().__init__(parent)
        self.protected_user_data = Cmd('PUD')

class Calibration(drv.Subsystem):
    """Table 4-10 -- Optional Calibration Command"""
    def __init__(self, parent):
        super().__init__(parent)
        self.self_calibration = Cmd("CAL?", access=Access.WO)

class Trigger(drv.Subsystem):
    """Table 4-11 -- Optional Trigger Command"""
    def __init__(self, parent):
        super().__init__(parent)
        self.trigger = Cmd("TRG", access=Access.WO)

class Macro(drv.Subsystem):
    """Table 4-12 -- Optional Trigger Macro Commands
        Table 4-13 -- Optional Macro Commands"""
    def __init__(self, parent):
        super().__init__(parent)
        self.trigger = Cmd("DDT", access=Access.WO)
        self.define = Cmd("DMC", access=Access.WO)
        self.enable = Cmd("EMC", access=Access.WO)
        self.contents = Cmd("GMC", access=Access.RO)
        self.learn = Cmd("LMC", access=Access.WO)
        self.purge = Cmd("PMC", access=Access.WO)

class Identification(drv.Subsystem):
    """Table 4-14 -- Optional Option Identification Command"""
    def __init__(self, parent):
        super().__init__(parent)
        self.identification_opt = Cmd("OPT", access=Access.RO)

class StoredSetting(drv.Subsystem):
    """Table 4-15 -- Optional Stored Setting Commands"""
    def __init__(self, parent):
        super().__init__(parent)
        self.recall = Cmd("RCL", access=Access.WO)
        self.save = Cmd("SAV", access=Access.WO)

class Learn(drv.Subsystem):
    """Table 4-16 -- Optional Learn Command"""
    def __init__(self, parent):
        super().__init__(parent)
        self.learn_device_setup = Cmd("LRN", access=Access.WO)

class SystemConfiguration(drv.Subsystem):
    """Table 4-18 -- Optional System Configuration Commands"""
    def __init__(self, parent):
        super().__init__(parent)
        self.accept_address_command = Cmd("AAD", access=Access.WO)
        self.disable_listener_function = Cmd("DLF", access=Access.WO)

class ControlPassing(drv.Subsystem):
    """Table 4-19 -- Optional Passing Control Commands"""
    def __init__(self, parent):
        super().__init__(parent)
        self.pass_back = Cmd("PCB", access=Access.WO)


class TestIeee488_2(unittest.TestCase):

    def setUp(self):
        from .ieee488_1 import Ieee4881
        class Driver(Ieee4881, Ieee4882): pass

        socket = drv.TesterSocket()
        socket.msg = {"*TST?\n": "1\n",
                      "*IDN?\n": "TEST, UNIT, 488, 2\n",
                      "*RST 2\n": "",
                      "*RST\n": "",
                      "*DC1\n": ""
                     }
        self.i = Driver(socket)

    def test_selfTestFailure(self):
        self.assertRaises(ieee.HardwareError, self.i.self_test.read)

    def test_read(self):
        self.assertEqual(self.i.identification.read()[1], "UNIT")

    def test_write(self):
        self.i.reset.write()

    def test_4881(self):
        self.i.clear_device.write()


if __name__ == "__main__":
    import logging
    logging.basicConfig()
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    unittest.main()
