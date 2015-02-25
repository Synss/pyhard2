# -*- coding: utf-8 -*-
"""Graphical user interface to Bronkhorst flow and pressure controllers."""

import sys
import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt

import pyhard2.ctrlr as ctrlr
from pyhard2.gui.programs import SetpointRampProgram
import pyhard2.driver.virtual as virtual
import pyhard2.driver as drv
from pyhard2.driver.bronkhorst import MFC


def createController():
    """Initialize controller."""
    config = ctrlr.Config("bronkhorst")
    if not config.nodes:
        config.nodes = range(10, 16)
        config.names = ["MFC%i" % node for node in config.nodes]
    if config.virtual:
        driver = virtual.VirtualInstrument()
        iface = ctrlr.Controller.virtualInstrumentController(config, driver)
    else:
        driver = MFC(drv.Serial(config.port))
        iface = ctrlr.Controller(config, driver)
        iface.addCommand(driver.direct_reading.measure, "measure",
                         poll=True, log=True)
        iface.addCommand(driver.direct_reading.setpoint, "setpoint",
                         log=True, specialColumn="programmable")
        iface.addCommand(driver.controller.valve_output, "output",
                         poll=True, log=True)
        iface.addCommand(driver.controller.PIDKp, "PID P", hide=True,
                         specialColumn="pidp")
        iface.addCommand(driver.controller.PIDKi, "PID I", hide=True,
                         specialColumn="pidi")
        iface.addCommand(driver.controller.PIDKd, "PID D", hide=True,
                         specialColumn="pidd")
    iface.programs.default_factory = SetpointRampProgram
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


