# -*- coding: utf-8 -*-
"""
Amtron GUI controllers
======================

Graphical user interface to Amtron CS400 laser controller.

"""

import sys
import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt

import pyhard2.ctrlr as ctrlr
import pyhard2.driver.virtual as virtual
from pyhard2.driver.amtron import CS400


def createController(opts):
    """Register `xxx` and `yyy`."""

    iface = ctrlr.SetpointController()
    iface.setWindowTitle(u"Amtron CS400 controller")
    if not opts.config:
        opts.config = {"virtual": [dict(name="CS400", driver="virtual")]}
    if opts.virtual:
        iface.setWindowTitle(iface.windowTitle() + u" [virtual]")
    # connections:
    #    thermometer      pid           laser
    #    measure      ->  compute   ->  output
    iface.addInstrumentClass(CS400, "CS400", dict(
        output="power.power",
        measure="thermometer.measure",
        setpoint="pid.setpoint",
        pid_gain="pid.gain",
        pid_integral="pid.integral",
        pid_derivative="pid.derivative",))
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
            opts.config = opts.config["amtron"]
        except KeyError:
            pass
    iface = createController(opts)
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)
