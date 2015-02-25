"""Graphical user interface to Fluke Series 18x multimeters."""

import sys

import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtGui

import pyhard2.ctrlr as ctrlr
from pyhard2.gui.programs import SetpointRampProgram
import pyhard2.driver as drv
import pyhard2.driver.virtual as virtual
import pyhard2.driver.fluke as fluke


def createController():
    """Initialize controller."""
    config = ctrlr.Config("fluke", "18x")
    if not config.nodes:
        config.nodes, config.names = ([0], ["Fluke 18x"])
    if config.virtual:
        driver = virtual.VirtualInstrument()
        iface = ctrlr.Controller.virtualInstrumentController(config, driver)
        iface.programs.default_factory = SetpointRampProgram
    else:
        driver = fluke.Fluke18x(drv.Serial(config.port))
        iface = ctrlr.Controller(config, driver)
        iface.addCommand(driver.measure, "Measure", poll=True, log=True)
        iface.addCommand(driver.unit, "Unit", poll=True)
    iface.populate()
    return iface


def main(argv):
    """Start controller."""
    app = QtGui.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    iface = createController()
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)
