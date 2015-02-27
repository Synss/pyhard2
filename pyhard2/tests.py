import sys
import unittest

import sip as _sip
for _type in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    _sip.setapi(_type, 2)

from PyQt4.QtGui import QApplication
from PyQt4.QtTest import QTest

from pyhard2.driver.virtual import VirtualInstrument
from pyhard2.gui.driver import DriverModel, DriverWidget
from pyhard2.gui.monitor import MonitorWidget
from pyhard2.gui.programs import ProgramWidget
import pyhard2.ctrlr.amtron as amtron
import pyhard2.ctrlr.bronkhorst as bronkhorst
import pyhard2.ctrlr.daq as daq
import pyhard2.ctrlr.deltaelektronika as deltaelektronika
import pyhard2.ctrlr.deltafluke as deltafluke
import pyhard2.ctrlr.fluke as fluke
import pyhard2.ctrlr.pfeiffer as pfeiffer
import pyhard2.ctrlr.watlow as watlow


class TestGui(unittest.TestCase):

    def setUp(self):
        self.app = QApplication(sys.argv)
        self.app.lastWindowClosed.connect(self.app.quit)

    def test_open_driverWidget(self):
        widget = DriverWidget()
        driver = VirtualInstrument()
        driverModel = DriverModel(driver, widget)
        widget.setDriverModel(driverModel)
        widget.populate()

    def test_open_monitorWidget(self):
        widget = MonitorWidget()
        driver = VirtualInstrument()
        driverModel = DriverModel(driver, widget)
        widget.setDriverModel(driverModel)
        widget.populate()

    def test_open_programWidget(self):
        widget = ProgramWidget()
        driver = VirtualInstrument()
        driverModel = DriverModel(driver, widget)
        widget.setDriverModel(driverModel)
        widget.populate()

    def test_amtron(self):
        amtron.createController()

    def test_bronkhorst(self):
        bronkhorst.createController()

    def test_daq(self):
        daq.createController()

    def test_deltaelektronika(self):
        deltaelektronika.createController()

    def test_deltafluke(self):
        return  # FIXME
        deltafluke.createController()

    def test_fluke(self):
        fluke.createController()

    def test_pfeiffer(self):
        pfeiffer.createController()

    def test_watlow(self):
        watlow.createController()


if __name__ == "__main__":
    unittest.main()
