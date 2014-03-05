# -*- coding: utf-8 -*-
"""
Pfeiffer GUI controllers
========================

Graphical user interface to Pfeiffer Maxigauge pressure controller.

"""

import sys

import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtGui

import pyhard2.ctrlr as ctrlr
import pyhard2.driver.virtual as virtual
import pyhard2.driver.pfeiffer as pfeiffer


class VirtualMaxigauge(virtual.VirtualInstrument):

    """Virtual instrument with a `node`."""

    def __init__(self, socket, async, node=0):
        super(VirtualMaxigauge, self).__init__()
        self.node = node


def createController(opts):
    """
    Register `VirtualMaxigauge` and `Maxigauge`.

    """
    iface = ctrlr.MonitorController()
    iface.setWindowTitle(u"Pfeiffer Maxigauge controller")
    if not opts.config:
        opts.config = {"virtual": [dict(name="G%i" % idx,
                                        extra={"node": idx},
                                        driver="virtual")
                                   for idx in range(1, 5)]}
    if opts.virtual:
        iface.setWindowTitle(iface.windowTitle() + u" [virtual]")
    iface.addInstrumentClass(pfeiffer.Maxigauge, "maxigauge")
    iface.addInstrumentClass(VirtualMaxigauge, "virtual",
                             virtual.virtual_mapper)
    iface.loadConfig(opts)
    return iface


def main(argv):
    """Start controller."""
    app = QtGui.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    opts = ctrlr.cmdline()
    if opts.config:
        try:
            opts.config = opts.config["pfeiffer"]
        except KeyError:
            pass
    iface = createController(opts)
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)
