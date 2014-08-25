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
import pyhard2.driver as drv
Cmd = drv.Command
import pyhard2.driver.virtual as virtual
from pyhard2.driver.watlow import Series988


class WatlowProgram(ctrlr.SingleShotProgram):

    """Program that can be used in combination with the ramping facility
    provided in hardware.

    Attributes:
        rate: The signal is emitted with the heating rate until the next
            setpoint.

    See also:
        The class inherits :class:`~pyhard2.ctrlr.SingleShotProgram`.

    """
    rate = Signal(float)

    def __init__(self):
        super(WatlowProgram, self).__init__()

    @Slot()
    def _shoot(self):
        self._index += 1
        try:
            rate = round(abs(60.0 * self._dv/self._dt))  # degree / min
            self.rate.emit(rate)
        except IndexError:
            QtCore.QTimer.singleShot(100, self.stop)
        else:
            # value at index + 1
            self.value.emit(self._profile.y(self._index + 1))
            self._timer.start(1000 * self._dt)


class _ComboBoxDelegate(QtGui.QAbstractItemDelegate):

    def __ini__(self, parent=None):
        super(_ComboBoxDelegate, self).__init__(parent)

    def setEditorData(self, editor, index):
        if not index.isValid(): return
        editor.setCurrentIndex(index.model().itemFromIndex(index).data())

    def setModelData(self, combobox, model, index):
        if not index.isValid(): return
        model.setData(index, combobox.currentIndex())


MeasureColumn = 0
SetpointColumn = 1
OutputColumn = 2
PidPColumn = 3
PidIColumn = 4
PidDColumn = 5
RampInitColumn = 6
RampRateColumn = 7


class WatlowController(ctrlr.Controller):

    """GUI controller with controls for hardware ramping.

    See also:
        The class inherits :class:`pyhard2.ctrlr.Controller`.

    """
    def __init__(self, parent=None):
        super(WatlowController, self).__init__(parent)
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
        self.ui.initCombo.setCurrentIndex(1)

        self.ui._layout = QtGui.QHBoxLayout(self.ui)
        self.ui._layout.addWidget(self.ui.initCombo)
        self.ui._layout.addWidget(self.ui.rateEdit)

        self.ui.rampSettings = QtGui.QWidget(self.ui)
        self.ui.rampSettings.setLayout(self.ui._layout)
        self.ui.instrumentPanel.layout().addWidget(self.ui.rampSettings)

        self.programPool.default_factory = WatlowProgram
        self._rampInitValuePool = {}
        self._rateValuePool = {}

        self.rampInitMapper = QtGui.QDataWidgetMapper(self)
        self.rampInitMapper.setModel(self._driverModel)
        self.rampInitMapper.setItemDelegate(_ComboBoxDelegate(self))
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

        self._specialColumnMapper.update(dict(
            rampinit=lambda column:
                     self.rampInitMapper.addMapping(self.ui.initCombo, column),
            rate=lambda column:
                 self.rateEditMapper.addMapping(self.ui.rateEdit, column)))

    def _disableRateEditOnNoRamp(self, currentIndex):
        self.ui.rateEdit.setDisabled(
            {"no ramp": True}.get(currentIndex, False))

    def _setupPrograms(self):
        super(WatlowController, self)._setupPrograms()
        if self._programmableColumn is None: return
        for row, program in self.programPool.iteritems():
            program.started.connect(
                lambda:
                self._driverModel.item(row, RampInitColumn).setData(2))
            program.rate.connect(
                lambda value:
                self._driverModel.item(row, RampRateColumn).setData(value))

            program.started.connect(partial(
                self.ui.rampSettings.setDisabled, True))
            program.finished.connect(partial(
                self.ui.rampSettings.setDisabled, False))
            program.finished.connect(partial(self.stopProgram, row))

    def startProgram(self, row):
        # save values
        self._rampInitValuePool[row] = self._driverModel.item(
            row, RampInitColumn).data()
        self._rateValuePool[row] = self._driverModel.item(
            row, RampRateColumn).data()
        super(WatlowController, self).startProgram(row)

    def stopProgram(self, row):
        # restore values
        self._driverModel.item(row, RampInitColumn).setData(
            self._rampInitValuePool.pop(row))
        self._driverModel.item(row, RampRateColumn).setData(
            self._rateValuePool.pop(row))


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
    args = ctrlr.Config("watlow")
    if args.virtual:
        driver = virtual.VirtualInstrument()
        driver.setup = drv.Subsystem(driver)
        driver.setup.setProtocol(drv.ObjectWrapperProtocol(_VirtualRamping()))
        driver.setup.global_ = drv.Subsystem(driver.setup)
        driver.setup.global_.ramp_init = Cmd("ramp_init")
        driver.setup.global_.ramp_rate = Cmd("ramp_rate")
        iface = WatlowController.virtualInstrumentController(driver, u"Watlow")
    else:
        driver = Series988(drv.Serial(args.port))
        iface = WatlowController(driver, u"Watlow")
        iface.addCommand(driver.temperature1, "measure", poll=True, log=True)
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
                       specialColumn="rate")
    iface.editorPrototype.default_factory=QtGui.QSpinBox
    iface.addNode(None, u"Watlow")
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
