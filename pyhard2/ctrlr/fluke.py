"""
Fluke GUI controllers
=====================

Graphical user interface to Fluke Series 18x multimeters.

"""

import sys

import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtGui

import pyhard2.ctrlr as ctrlr
import pyhard2.driver.virtual as virtual
import pyhard2.driver.fluke as fluke


def createController(opts):
    """
    Register `VirtualInstrument` and `Fl18x`.

    """
    iface = ctrlr.MonitorController()
    iface.setWindowTitle(u"Fluke 18x Controller")
    if not opts.config:
        opts.config = {"virtual": [dict(name="Fluke 18x", driver="virtual")]}
    if opts.virtual:
        iface.setWindowTitle(iface.windowTitle() + u" [virtual]")
    iface.addInstrumentClass(virtual.VirtualInstrument, "virtual",
                             virtual.virtual_mapper)
    iface.addInstrumentClass(fluke.Fl18x, "fluke18x")
    iface.loadConfig(opts)
    return iface


def main(argv):
    """Start controller."""
    app = QtGui.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    opts = ctrlr.cmdline()
    if opts.config:
        try:
            opts.config = opts.config["fluke"]
        except KeyError:
            pass
    iface = createController(opts)
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)
