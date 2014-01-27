import pyhard2.driver as drv
Action, Param = drv.Action, drv.Parameter

import ieee488_1
IeeeProtocol = ieee488_1.IeeeProtocol


__all__ = ["Ieee488_2", "Mandatory"]


def parse_idn(msg):
    """returns (manufacturer, model, serial_number, firmware level)"""
    return msg.split(",")


class Mandatory(drv.Subsystem):
    """Mandatory commands in the 488.2 standard."""

    # Table 4-4 -- Required Status Reporting Common Commands
    # Table 4-7 -- Required Internal Operation Common Commands
    # Table 4-17 -- Required Synchronization Commands

    # Table 10-2
    # System data
    identification = Param('IDN', getter_func=parse_idn, read_only=True,
                           doc="Identification query")
    # Internal operations
    reset = Action("RST")  # OK
    self_test = Action("TST?")  # response of 0: no error else raise
    # Synch
    operation_completed = Param('OPC')  # reponse 1, see 12.5.3
    wait_to_continue = Action("WAI")  # see 12.5.1
    # Status & Event
    clear_status = Action("CLS")  # OK
    event_status_enable = Param('ESE')  # see 11.4.2.3
    event_status_register = Param('ESR', read_only=True)  # see 11.5.1.2
    service_request_enable = Param('SRE', minimum=0, maximum=255)  # see 11.3.2
    status_byte = Param('STB', read_only=True)


class Optional(drv.Subsystem):

    # Table 4-5 -- Optional Power-On Common Commands
    clear_poweron_status = Action("PSC")
    poweron_status = Param("PSC", read_only=True)

    # Table 4-6 -- Optional Parallel Poll Common Commands
    individual_status = Param('IST', read_only=True)
    parallel_poll_enable_register = Param('PRE')  # command/query

    # Table 4-8 -- Optional Resource Description Common Command
    resource_description_transfer = Param('RDT')

    # Table 4-9 -- Optional Protected User Data Command
    protected_user_data = Param('PUD')

    # Table 4-10 -- Optional Calibration Command
    self_calibration = Action("CAL?")

    # Table 4-11 -- Optional Trigger Command
    trigger = Action("TRG")

    # Table 4-12 -- Optional Trigger Macro Commands
    trigger_macro = Action("DDT")

    # Table 4-13 -- Optional Macro Commands
    define_macro = Action("DMC")
    enable_macro = Action("EMC")
    macro_contents = Param("GMC", read_only=True)
    learn_macro = Action("LMC")
    purge_macro = Action("PMC")

    # Table 4-14 -- Optional Option Identification Command
    identification_opt = Param("OPT", read_only=True)

    # Table 4-15 -- Optional Stored Setting Commands
    recall = Action("RCL")
    save = Action("SAV")

    # Table 4-16 -- Optional Learn Command
    learn_device_setup = Action("LRN")


    # Table 4-18 -- Optional System Configuration Commands
    accept_address_command = Action("AAD")
    disable_listener_function = Action("DLF")

    # Table 4-19 -- Optional Passing Control Commands
    pass_control_back = Action("PCB")


class Ieee488_2(drv.Instrument):

    def __init__(self, socket):
        socket.newline = "\n"
        protocol = IeeeProtocol()
        super(Ieee488_2, self).__init__(socket, protocol)
        self.ieee488_1 = ieee488_1.mandatory(self)
        self.mandatory = Mandatory(self)
        self.default = "mandatory"

