# -*- coding: utf-8 -*-
"""
Bronkhorst GUI controllers
==========================

Graphical user interface to Bronkhorst flow and pressure controllers.

"""

import sys
import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt

import pyhard2.ctrlr as ctrlr
import pyhard2.driver.virtual as virtual
from pyhard2.driver.bronkhorst import MFC, PC


class VirtualBronkhorstInstrument(virtual.VirtualInstrument):

    """Virtual instrument with a `node`."""

    def __init__(self, socket, async=False, node=128):
        super(VirtualBronkhorstInstrument, self).__init__(socket, async)
        self.node = node


def createController(opts):
    """
    Register VirtualBronkhorstInstrument, PC and MFC.

    """
    iface = ctrlr.SetpointController()
    iface.setWindowTitle(u"Bronkhorst controller")
    if not opts.config:
        opts.config = {"virtual": [dict(name="Instr %i" % idx,
                                        extra={"node": idx},
                                        driver="virtual")
                                   for idx in range(10, 17)]}
    if opts.virtual:
        iface.setWindowTitle(iface.windowTitle() + u" [virtual]")
    iface.addInstrumentClass(VirtualBronkhorstInstrument, "virtual",
                             virtual.virtual_mapper)
    bronkhorstMapper = dict(
        output="controller.valve_output",
        measure="direct_reading.fmeasure",
        setpoint="direct_reading.fsetpoint",
        pid_gain="controller.PIDKp",
        pid_derivative="controller.PIDKd",
        pid_integral="controller.PIDKi",
        valve_mode="control_mode")
    iface.addInstrumentClass(PC, "PC", bronkhorstMapper)
    iface.addInstrumentClass(MFC, "MFC", bronkhorstMapper)
    iface.loadConfig(opts)
    return iface


def main(argv):
    """Start controller."""
    app = QtGui.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    opts = ctrlr.cmdline()
    if opts.config:
        try:
            opts.config = opts.config["bronkhorst"]
        except KeyError:
            pass
    iface = createController(opts)
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)


