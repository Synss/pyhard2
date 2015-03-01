# -*- coding: utf-8 -*-
"""Graphical user interface to Watlow Series988 temperature controller."""

import sys
from functools import partial

from PyQt5 import QtWidgets, QtCore
Signal, Slot = QtCore.pyqtSignal, QtCore.pyqtSlot

from pyhard2.gui.driver import DriverWidget
from pyhard2.gui.controller import Config, Controller
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
        super().__init__()

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


class WatlowDriverWidget(DriverWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rateEdit = QtWidgets.QSpinBox(self, enabled=False,
                                           minimum=0, maximum=9999)
        self.initCombo = QtWidgets.QComboBox(self)
        self.initCombo.addItems([
            "no ramp",
            "on startup",
            "on setpoint change"
        ])
        self.initCombo.currentIndexChanged[str].connect(
            lambda current: self.rateEdit.setDisabled(current == "no ramp"))

        self.rampLayout = QtWidgets.QHBoxLayout()
        self.rampLayout.addWidget(self.initCombo)
        self.rampLayout.addWidget(self.rateEdit)
        self.verticalLayout.addLayout(self.rampLayout)

        self.rampInitMapper = QtWidgets.QDataWidgetMapper(self)
        self.rampInitMapper.setItemDelegate(ComboBoxDelegate(self))
        self.initCombo.currentIndexChanged[int].connect(
            self.rampInitMapper.submit)
        self.rateEditMapper = QtWidgets.QDataWidgetMapper(self)
        self.rateEdit.valueChanged.connect(self.rateEditMapper.submit)

    def setDriverModel(self, model):
        super().setDriverModel(model)
        self.rampInitMapper.setModel(model)
        self.rateEditMapper.setModel(model)

    def mapRampInitComboBox(self, column):
        assert(self.rampInitMapper.model())
        self.rampInitMapper.addMapping(self.initCombo, column)

    def mapRateEditor(self, column):
        assert(self.rateEditMapper.model())
        self.rateEditMapper.addMapping(self.rateEdit, column)


class WatlowController(Controller):

    def __init__(self, config, driver, parent=None):
        super().__init__(config, driver, parent)
        self.programs.default_factory = WatlowProgram

        self.rampInitColumn = None
        self.rampRateColumn = None
        self._rampInitValuePool = {}
        self._rateValuePool = {}

        self._roleMapper.update(dict(
            rampinit=self.setRampInitColumn,
            ramprate=self.setRampRateColumn))

    def _addDriverWidget(self):
        super()._addDriverWidget(WatlowDriverWidget)

    def _currentRowChanged(self, current, previous):
        super()._currentRowChanged(current, previous)
        self.driverWidget.rampInitMapper.setCurrentModelIndex(current)
        self.driverWidget.rateEditMapper.setCurrentModelIndex(current)

    def populate(self):
        super().populate()
        self.driverWidget.rampInitMapper.toFirst()
        self.driverWidget.rampInitMapper.toFirst()

    def setRampInitColumn(self, column):
        self.rampInitColumn = column
        self.driverWidget.mapRampInitComboBox(column)

    def setRampRateColumn(self, column):
        self.rampRateColumn = column
        self.driverWidget.mapRateEditor(column)

    def startProgram(self, row):
        if self.programColumn() is None:
            return
        program = self.programs[row]
        # Connect program to GUI
        program.started.connect(
            lambda:
            self.driverModel.item(row, self.rampInitColumn).setData(2))
        program.rate.connect(
            lambda value:
            self.driverModel.item(row, self.rampRateColumn).setData(value))
        program.started.connect(partial(
            self.driverWidget.rateEdit.setDisabled, True))
        program.finished.connect(partial(
            self.driverWidget.rateEdit.setDisabled, False))
        # Save values
        self._rampInitValuePool[row] = self.driverModel.item(
            row, self.rampInitColumn).data()
        self._rateValuePool[row] = self.driverModel.item(
            row, self.rampRateColumn).data()
        super().startProgram(row)

    def stopProgram(self, row):
        # restore values
        self.driverModel.item(row, self.rampInitColumn).setData(
            self._rampInitValuePool.pop(row))
        self.driverModel.item(row, self.rampRateColumn).setData(
            self._rateValuePool.pop(row))
        super().stopProgram(row)


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
    config = Config("watlow")
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
        iface.addCommand(driver.temperature1, "TC sample")
        iface.addCommand(driver.temperature2, "TC heater")
        iface.addCommand(driver.setpoint, "setpoint", role="program")
        iface.addCommand(driver.power, "output")
        iface.addCommand(driver.operation.pid.a1.gain, "PID P", hide=True,
                         role="pidp")
        iface.addCommand(driver.operation.pid.a1.integral, "PID I", hide=True,
                         role="pidi")
        iface.addCommand(driver.operation.pid.a1.derivative, "PID D",
                         hide=True, role="pidd")
    iface.addCommand(driver.setup.global_.ramp_init, "ramp_init",
                     hide=True, role="rampinit")
    iface.addCommand(driver.setup.global_.ramp_rate, "ramp_rate",
                     hide=True, role="ramprate")
    iface.editorPrototype.default_factory = QtWidgets.QSpinBox
    # Make sure we can read the rate
    driver.setup.global_.ramp_init.write(1)
    iface.populate()
    return iface


def main(argv):
    """Start controller."""
    app = QtWidgets.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    iface = createController()
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)
