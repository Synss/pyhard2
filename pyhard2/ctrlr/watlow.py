# -*- coding: utf-8 -*-
"""Graphical user interface to Watlow Series988 temperature controller."""

import sys
import sip
from functools import partial
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtCore, QtGui
Signal, Slot = QtCore.pyqtSignal, QtCore.pyqtSlot
Qt = QtCore.Qt

import pyhard2.ctrlr as ctrlr
from pyhard2.gui.programs import SingleShotProgram
from pyhard2.gui.delegates import ComboBoxDelegate
import pyhard2.driver as drv
Cmd = drv.Command
import pyhard2.driver.virtual as virtual
from pyhard2.driver.watlow import Series988


class WatlowProgram(SingleShotProgram):

    """Program that can be used in combination with the ramping facility
    provided in hardware.

    Attributes:
        rate: The signal is emitted with the heating rate until the next
            setpoint.

    See also:
        The class inherits :class:`~pyhard2.gui.programs.SingleShotProgram`.

    """
    rate = Signal(float)

    def __init__(self):
        super(WatlowProgram, self).__init__()

    @Slot()
    def _shoot(self):
        self._index += 1
        try:
            rate = round(abs(60.0 * self._dv/self._dt))  # degree / min
        except IndexError:
            self.stop()
        else:
            self.rate.emit(rate)
            # value at index + 1
            self.value.emit(self._profile.y(self._index + 1))
            self._timer.start(1000 * self._dt)


class WatlowController(ctrlr.Controller):

    def __init__(self, config, driver, uifile="", parent=None):
        super(WatlowController, self).__init__(config, driver, uifile, parent)
        self.programs.default_factory = WatlowProgram
        self.rampInitColumn = None
        self.rampRateColumn = None
        self._rampInitValuePool = {}
        self._rateValuePool = {}

        self.ui.initCombo = QtGui.QComboBox(self.ui)
        self.ui.initCombo.addItems([
            "no ramp",
            "on startup",
            "on setpoint change"
        ])

        self.ui.rateEdit = QtGui.QSpinBox(self.ui)
        self.ui.rateEdit.setRange(0, 9999)

        self.ui.initCombo.currentIndexChanged[str].connect(
            self._disableRateEditOnNoRamp)

        self.ui.rampSettings = QtGui.QWidget(self.ui)
        self.ui.instrumentPanel.layout().addWidget(self.ui.rampSettings)
        self.ui._layout = QtGui.QHBoxLayout(self.ui.rampSettings)
        self.ui._layout.addWidget(self.ui.initCombo)
        self.ui._layout.addWidget(self.ui.rateEdit)

        self._specialColumnMapper.update(dict(
            rampinit=self.setRampInitColumn,
            ramprate=self.setRampRateColumn))

        self.rampInitMapper = QtGui.QDataWidgetMapper(self)
        self.rampInitMapper.setModel(self._driverModel)
        self.rampInitMapper.setItemDelegate(ComboBoxDelegate(self))
        self.ui.driverView.selectionModel().currentRowChanged.connect(
            self.rampInitMapper.setCurrentModelIndex)
        self.populated.connect(self.rampInitMapper.toFirst)
        self.ui.initCombo.currentIndexChanged[int].connect(
            self.rampInitMapper.submit)

        self.rateEditMapper = QtGui.QDataWidgetMapper(self)
        self.rateEditMapper.setModel(self._driverModel)
        self.ui.driverView.selectionModel().currentRowChanged.connect(
            self.rateEditMapper.setCurrentModelIndex)
        self.populated.connect(self.rampInitMapper.toFirst)
        self.ui.rateEdit.valueChanged.connect(self.rateEditMapper.submit)

    def _disableRateEditOnNoRamp(self, currentIndex):
        self.ui.rateEdit.setDisabled(
            {"no ramp": True}.get(currentIndex, False))

    def setRampRateColumn(self, column):
        """Set ramp rate column to `column`."""
        self.rampRateColumn = column
        self.rateEditMapper.addMapping(self.ui.rateEdit, column)

    def setRampInitColumn(self, column):
        """Set ramp init column to `column`."""
        self.rampInitColumn = column
        self.rampInitMapper.addMapping(self.ui.initCombo, column)

    def startProgram(self, row):
        if self.programmableColumn() is None:
            return
        program = self.programs[row]
        # Connect program to GUI
        program.started.connect(
            lambda:
            self._driverModel.item(row, self.rampInitColumn).setData(2))
        program.rate.connect(
            lambda value:
            self._driverModel.item(row, self.rampRateColumn).setData(value))
        program.started.connect(partial(
            self.ui.rampSettings.setDisabled, True))
        program.finished.connect(partial(
            self.ui.rampSettings.setDisabled, False))
        # Save values
        self._rampInitValuePool[row] = self._driverModel.item(
            row, self.rampInitColumn).data()
        self._rateValuePool[row] = self._driverModel.item(
            row, self.rampRateColumn).data()
        super(WatlowController, self).startProgram(row)

    def stopProgram(self, row):
        # restore values
        self._driverModel.item(row, self.rampInitColumn).setData(
            self._rampInitValuePool.pop(row))
        self._driverModel.item(row, self.rampRateColumn).setData(
            self._rateValuePool.pop(row))
        super(WatlowController, self).stopProgram(row)


class _VirtualRamping(object):

    def __init__(self):
        self.ramp_init = 0
        self._ramp_rate = 100

    @property
    def ramp_rate(self):
        #if self.ramp_init is 0:
        #    raise drv.HardwareError("Prompt not active")
        return self._ramp_rate

    @ramp_rate.setter
    def ramp_rate(self, ramp_rate):
        self._ramp_rate = ramp_rate


def createController():
    """Initialize controller."""
    config = ctrlr.Config("watlow")
    if not config.nodes:
        config.nodes = [None]
    if config.virtual:
        driver = virtual.VirtualInstrument()
        driver.setup = drv.Subsystem(driver)
        driver.setup.setProtocol(drv.ObjectWrapperProtocol(_VirtualRamping()))
        driver.setup.global_ = drv.Subsystem(driver.setup)
        driver.setup.global_.ramp_init = Cmd("ramp_init")
        driver.setup.global_.ramp_rate = Cmd("ramp_rate")
        iface = WatlowController.virtualInstrumentController(config, driver)
    else:
        driver = Series988(drv.Serial(config.port))
        iface = WatlowController(config, driver)
        iface.addCommand(driver.temperature1, "TC sample", poll=True, log=True)
        iface.addCommand(driver.temperature2, "TC heater", poll=True, log=True)
        iface.addCommand(driver.setpoint, "setpoint", log=True,
                         specialColumn="programmable")
        iface.addCommand(driver.power, "output", poll=True, log=True)
        iface.addCommand(driver.operation.pid.a1.gain, "PID P", hide=True,
                         specialColumn="pidp")
        iface.addCommand(driver.operation.pid.a1.integral, "PID I", hide=True,
                         specialColumn="pidi")
        iface.addCommand(driver.operation.pid.a1.derivative, "PID D", hide=True,
                         specialColumn="pidd")
    iface.addCommand(driver.setup.global_.ramp_init, "ramp_init", hide=True,
                     specialColumn="rampinit")
    iface.addCommand(driver.setup.global_.ramp_rate, "ramp_rate", hide=True,
                     specialColumn="ramprate")
    iface.editorPrototype.default_factory=QtGui.QSpinBox
    # Make sure we can read the rate
    driver.setup.global_.ramp_init.write(1)
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
