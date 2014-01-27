# -*- coding: utf-8 -*-
"""
Watlow GUI controllers
======================

Graphical user interface to Watlow Series988 temperature controller.

"""

import sys
import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt

import pyhard2.ctrlr as ctrlr
import pyhard2.driver.virtual as virtual
from pyhard2.driver.watlow import Series988


def createController(opts):
    """Register `VirtualWatlowInstrument` and `Series988`."""

    iface = ctrlr.SetpointController()
    iface.setWindowTitle(u"Watlow controller")
    if not opts.config:
        opts.config = {"virtual": [dict(name="Series 988", driver="virtual")]}
    if opts.virtual:
        iface.setWindowTitle(iface.windowTitle() + u" [virtual]")
    iface.addInstrumentClass(Series988, "Series988", dict(
        output="power",
        measure="temperature1",
        setpoint="setpoint",
        pid_gain="operation_pid_A.gain",
        pid_integral="operation_pid_A.integral",
        pid_derivative="operation_pid_A.derivative",))
    iface.addInstrumentClass(virtual.VirtualInstrument, "virtual",
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
            opts.config = opts.config["watlow"]
        except KeyError:
            pass
    iface = createController(opts)
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)
