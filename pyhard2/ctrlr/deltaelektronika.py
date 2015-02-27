"""Graphical user interface to Delta-Elektronika SM-700 Series
controllers."""


import sys
from pyhard2.gui.controller import Config, Controller
import pyhard2.driver as drv
import pyhard2.driver.virtual as virtual
import pyhard2.driver.deltaelektronika as delta


def createController():
    """Initialize controller."""
    config = Config("deltaelektronika", "SM-700")
    if not config.nodes:
        config.nodes, config.names = ([1], ["SM700"])
    if config.virtual:
        driver = virtual.VirtualInstrument()
        iface = Controller.virtualInstrumentController(config, driver)
    else:
        driver = delta.Sm700Series(drv.Serial(config.port))
        iface = Controller(config, driver)
        iface.addCommand(driver.source.voltage, "Voltage", poll=True, log=True)
        iface.addCommand(driver.source.current, "Current", poll=True, log=True)
    iface.populate()
    return iface


def main(argv):
    """Start controller."""
    from PyQt4 import QtGui
    app = QtGui.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    iface = createController()
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)
