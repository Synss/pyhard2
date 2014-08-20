import os.path
import pyhard2.driver as drv
from pyhard2.driver.aml import Ngc2d
from pyhard2.driver.amtron import CS400
from pyhard2.driver.bronkhorst import Controller
#from pyhard2.driver.daq import Ni622x
from pyhard2.driver.deltaelektronika import DplInstrument
from pyhard2.driver.digitek import DT80k
from pyhard2.driver.fluke import Fluke18x
from pyhard2.driver.ieee.scpi import ScpiPowerSupply, ScpiDCVoltmeter
from pyhard2.driver.keithley import Model6487
from pyhard2.driver.peaktech import Pt1885
from pyhard2.driver.pfeiffer import Maxigauge
from pyhard2.driver.virtual import VirtualInstrument
from pyhard2.driver.watlow import Series988

from graph import generate_graph

for driver_type in (Ngc2d,
                    CS400,
                    Controller,
                    #Ni622x,
                    DplInstrument,
                    DT80k,
                    Fluke18x,
                    ScpiPowerSupply,
                    ScpiDCVoltmeter,
                    Model6487,
                    Pt1885,
                    Maxigauge,
                    VirtualInstrument,
                    Series988):
    driver = driver_type(drv.TesterSocket())
    name = driver.__class__.__name__
    generate_graph(name, driver, os.path.join("documentation", "gv",
                                              ".".join((name, "txt"))))

