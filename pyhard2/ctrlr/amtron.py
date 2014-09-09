# -*- coding: utf-8 -*-
"""Graphical user interface to Amtron CS400 laser controller."""

import sys
import sip
from functools import partial
from operator import mul
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt

import pyhard2.ctrlr as ctrlr
import pyhard2.driver as drv
Cmd = drv.Command
import pyhard2.driver.virtual as virtual
import pyhard2.driver.amtron as amtron
import pyhard2.driver.daq as daq


class _ButtonDelegate(QtGui.QAbstractItemDelegate):

    def __init__(self, parent=None):
        super(_ButtonDelegate, self).__init__(parent)

    def setEditorData(self, editor, index):
        if not index.isValid(): return
        editor.setChecked(index.data() is True)

    def setModelData(self, editor, model, index):
        if not index.isValid(): return
        model.setData(index, editor.isChecked())


class AmtronController(ctrlr.Controller):

    def __init__(self, driver, windowTitle="", uifile="", parent=None):
        super(AmtronController, self).__init__(driver, windowTitle,
                                               uifile, parent)

        self.ui.powerBtn = QtGui.QPushButton(u"Power", checkable=True)
        self.ui.gateBtn = QtGui.QPushButton(u"Gate", checkable=True)

        self.ui._layout = QtGui.QHBoxLayout()
        self.ui._layout.addWidget(self.ui.powerBtn)
        self.ui._layout.addWidget(self.ui.gateBtn)
        self.ui.instrumentPanel.layout().addLayout(self.ui._layout)

        self.programPool.default_factory = ctrlr.SetpointRampProgram

        self.powerBtnMapper = QtGui.QDataWidgetMapper(self.ui.powerBtn)
        self.powerBtnMapper.setModel(self._driverModel)
        self.powerBtnMapper.setItemDelegate(_ButtonDelegate(self.powerBtnMapper))
        self.ui.driverView.selectionModel().currentRowChanged.connect(
            self.powerBtnMapper.setCurrentModelIndex)
        self.populated.connect(self.powerBtnMapper.toFirst)
        self.ui.powerBtn.toggled.connect(self.powerBtnMapper.submit)

        self.gateBtnMapper = QtGui.QDataWidgetMapper(self.ui.gateBtn)
        self.gateBtnMapper.setModel(self._driverModel)
        self.gateBtnMapper.setItemDelegate(_ButtonDelegate(self.gateBtnMapper))
        self.ui.driverView.selectionModel().currentRowChanged.connect(
            self.gateBtnMapper.setCurrentModelIndex)
        self.populated.connect(self.gateBtnMapper.toFirst)
        self.ui.gateBtn.toggled.connect(self.gateBtnMapper.submit)

        self._specialColumnMapper.update(dict(
            laserpower=lambda column:
                       self.powerBtnMapper.addMapping(self.ui.powerBtn, column),
            lasergate=lambda column:
                      self.gateBtnMapper.addMapping(self.ui.gateBtn, column)))


class AmtronDaq(drv.Subsystem):

    """
    Instrument using the DAQ for input (temperature) and the CS400 for
    output (laser power).  Output is controller by a PID.

    """
    # connections:
    #    thermometer      pid           laser
    #    measure      ->  compute   ->  output
    def __init__(self, serial, daqline):
        super(AmtronDaq, self).__init__()
        self.pid = virtual.PidSubsystem(spmin=-100.0, spmax=1000.0)
        self.temperature = daq.AiCommand(daqline, rfunc=partial(mul, 100))
        self.laser = amtron.CS400(serial)
        self.laser.control.control_mode.write(amtron.ControlMode.POWER)
        self.laser.command.laser_state.write(False)
        # Connections
        self.temperature.signal.connect(self.pid.measure.write)
        self.temperature.signal.connect(self.pid.output.read)
        self.pid.output.signal.connect(self.laser.set_total_power)


class _VirtualCommand(object):

    def __init__(self):
        self.laser_state = False
        self.gate_state = False


class VirtualAmtronInstrument(virtual.VirtualInstrument):

    def __init__(self):
        super(VirtualAmtronInstrument, self).__init__()
        self.command = drv.Subsystem(self)
        self.command.setProtocol(drv.ObjectWrapperProtocol(_VirtualCommand()))
        self.command.laser_state = Cmd("laser_state")
        self.command.gate_state = Cmd("gate_state")


def createController():
    """Initialize controller."""
    args = ctrlr.Config("amtron")
    if args.virtual:
        driver = VirtualAmtronInstrument()
        iface = AmtronController.virtualInstrumentController(
            driver, u"Amtron CS400")
    else:
        driver = AmtronDaq(drv.Serial(args.port))
        iface = AmtronController(driver, u"Amtron CS400")
        iface.addCommand(driver.input.measure, "measure", poll=True, log=True)
        iface.addCommand(driver.pid.setpoint, "setpoint",
                         log=True, specialColumn="programmable")
        iface.addCommand(driver.output.total_power, "power",
                         poll=True, log=True)
        iface.addCommand(driver.pid.proportional, "PID P", hide=True,
                         specialColumn="pidp")
        iface.addCommand(driver.pid.integral_time, "PID I", hide=True,
                         specialColumn="pidi")
        iface.addCommand(driver.pid.derivative_time, "PID D", hide=True,
                         specialColumn="pidd")
    iface.addCommand(driver.command.laser_state, "power", hide=True,
                     poll=True, specialColumn="laserpower")
    iface.addCommand(driver.command.gate_state, "gate", hide=True,
                     poll=True, specialColumn="lasergate")
    iface.addNode(0, "CS400")
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
