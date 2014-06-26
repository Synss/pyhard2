"""Graphical user interface to Fluke Series 18x multimeters."""

import sys

import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtGui

import pyhard2.ctrlr as ctrlr
import pyhard2.driver as drv
import pyhard2.driver.virtual as virtual
import pyhard2.driver.fluke as fluke


def createController():
    """Initialize controller"""
    args = ctrlr.Config("fluke")
    if args.virtual:
        driver = virtual.VirtualInstrument()
        iface = ctrlr.Controller.virtualInstrumentController(
            driver, u"Fluke 18x")
        iface.programPool.default_factory = ctrlr.SetpointRampProgram
    else:
        driver = fluke.Fluke18x(drv.Serial(args.port))
        iface = ctrlr.Controller(driver, u"Fluke 18x")
        iface.addCommand("measure", poll=True, log=True)
    iface.addNode(None, "Fluke 18x")
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
