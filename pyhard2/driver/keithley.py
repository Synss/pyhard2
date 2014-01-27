from scpi import *


class ScpiKeithleyCalculate(ScpiSubsystem):

    calc = """
    CALC:
      FORM: format  # <name>
      KMAT:
        MMF: m_factor  # <NRf>
        MA1: ma1  # same as MMF
        MBF: b_factor
        MA0F: ma0f  # same as MBF
        MUN: m_units  # <name>
      STAT: state  # bool
      DATA:
        ? '':
          - data
          - {read_only: true}
        LAT:
          - last_reading
          - {read_only: true}
    """

    calc2 = """
    CALC2:
      # FEED: write only
      LIM:
        UPP:
          DATA:
          - upper_limit
          - minimum=-9.99999e20
          - maximum=9.99999e20
          SOUR2:
          - fail_pattern
          - minimum=0
          - maximum=15
        STAT: enable_limit_testing
        FAIL:
        - test  # return limit of lim test
        - {read_only: true}
          """

class ScpiKeithleyDisplay(ScpiSubsystem):
    
    disp = """
    DISP:
      DIG:
      - resolution
      - minimum=4
      - maximum=7
      ENAB: enable_display  # bool
      WIND:
        TEXT:
          DATA: value
          STAT: enable_text_message
          """


class ScpiKeithleyFormat(ScpiSubsystem):
    pass


class ScpiKeithleySense(ScpiSubsystem):
    pass


class ScpiKeithleySource(ScpiSubsystem):
    pass


class ScpiKeithleyTrace(ScpiSubsystem):
    pass


class ScpiKeithleyTrigger(ScpiSubsystem):
    pass


class Keithley(Instrument):

    def __init__(self, socket):
        super(SCPIKeithley, self).__init__(socket)
        protocol = ScpiProtocol(socket)
        self.system = SCPIKeithleySystem(protocol)
        self.status = SCPIKeithleyStatus(protocol)
        self.calculate = SCPIKeithleyCalculate(protocol)
        self.display = SCPIKeithleyDisplay(protocol)
        self.format = SCPIKeithleyFormat(protocol)
        self.sense = SCPIKeithleySense(protocol)
        self.source = SCPIKeithleySource(protocol)
        self.trace = SCPIKeithleyTrace(protocol)
        self.trigger = SCPIKeithleyTrigger(protocol)
