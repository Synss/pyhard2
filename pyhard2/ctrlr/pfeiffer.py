# -*- coding: utf-8 -*-
"""Graphical user interface to Pfeiffer Maxigauge pressure controller."""

import sys
from itertools import izip_longest

import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtGui

import pyhard2.ctrlr as ctrlr
import pyhard2.driver as drv
from pyhard2.driver.pfeiffer import Maxigauge
import pyhard2.driver.virtual as virtual


def createController():
    """Initialize controller."""
    config = ctrlr.Config("pfeiffer", "Multigauge")
    if not config.nodes:
        config.nodes = range(6)
    if not config.nodes:
        config.nodes = range(1, 7)
        config.names = ["G%i" % node for node in config.nodes]
    if config.virtual:
        driver = virtual.VirtualInstrument()
        iface = ctrlr.Controller.virtualInstrumentController(config, driver)
        iface.programPool.default_factory = ctrlr.SetpointRampProgram
    else:
        driver = Maxigauge(drv.Serial(config.port))
        iface = ctrlr.Controller(config, driver)
        iface.editorPrototype.default_factory = ctrlr.ScientificSpinBox
        iface.addCommand(driver.gauge.pressure, u"pressure", poll=True, log=True)
    iface.ui.driverView.setItemDelegateForColumn(
        0, ctrlr.FormatTextDelegate("%.2e"))
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
