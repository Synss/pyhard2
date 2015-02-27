# -*- coding: utf-8 -*-
"""Graphical user interface to NI-DAQ and comedi-compatible data
acquisition hardware.

"""
import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtCore, QtGui, QtSvg
Qt = QtCore.Qt
import pyhard2.rsc

from pyhard2.gui.controller import Config, Controller
from pyhard2.gui.delegates import ButtonDelegate
import pyhard2.driver as drv
Cmd = drv.Command
import pyhard2.driver.daq as daq


class ValveButton(QtGui.QAbstractButton):

    """Button displaying the image of a valve."""

    def __init__(self, parent=None):
        super(ValveButton, self).__init__(parent)
        self.setCheckable(True)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self._rendererOn = QtSvg.QSvgRenderer(self)
        self._rendererOff = QtSvg.QSvgRenderer(self)
        self._rendererOn.load(":/img/valve_green.svg")
        self._rendererOff.load(":/img/valve_red.svg")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        if self.isChecked():
            self._rendererOn.render(painter)
        else:
            self._rendererOff.render(painter)

    def sizeHint(self):
        if self.isChecked():
            return self._rendererOn.defaultSize()
        else:
            return self._rendererOff.defaultSize()


class VirtualDaq(QtCore.QObject):

    class Dio(object):

        def __init__(self):
            self.state = False

    class Aio(object):

        def __init__(self):
            self.ai = 0
            self.ao = 0

    def __init__(self, device, parent=None):
        super(VirtualDaq, self).__init__(parent)
        self.digitalIO = drv.Subsystem()
        self.digitalIO.setProtocol(drv.ObjectWrapperProtocol(VirtualDaq.Dio()))
        self.digitalIO.state = Cmd("state")
        self.voltage = drv.Subsystem()
        self.voltage.setProtocol(drv.ObjectWrapperProtocol(VirtualDaq.Aio()))
        self.voltage.ai = Cmd("ai")
        self.voltage.ao = Cmd("ao")


def createController():
    """Initialize controller."""
    config = Config("daq")
    if not config.nodes:
        config.nodes = range(20)
        config.names = ["V%i" % node for node in config.nodes]
    if config.virtual:
        driver = VirtualDaq(config.port)
    else:
        driver = daq.Daq(config.port)
    iface = Controller(config, driver)
    iface.addCommand(driver.digitalIO.state, "state")
    iface.editorPrototype.default_factory = ValveButton
    iface.driverWidget.driverView.setItemDelegateForColumn(
        0, ButtonDelegate(ValveButton(), iface))
    iface.driverWidget.driverView.setEditTriggers(
        QtGui.QAbstractItemView.SelectedClicked |
        QtGui.QAbstractItemView.CurrentChanged)
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
    import sys
    main(sys.argv)
