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

    def __init__(self, config, driver, uifile="", parent=None):
        super(AmtronController, self).__init__(config, driver, uifile, parent)

        self.ui.powerBtn = QtGui.QPushButton(u"Power", checkable=True)
        self.ui.gateBtn = QtGui.QPushButton(u"Gate", checkable=True)
        self.ui.pilotBtn = QtGui.QPushButton(u"Pilot laser", checkable=True)

        self.ui._layout = QtGui.QHBoxLayout()
        self.ui._layout.addWidget(self.ui.powerBtn)
        self.ui._layout.addWidget(self.ui.gateBtn)
        self.ui._layout.addWidget(self.ui.pilotBtn)
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

        self.pilotBtnMapper = QtGui.QDataWidgetMapper(self.ui.pilotBtn)
        self.pilotBtnMapper.setModel(self._driverModel)
        self.pilotBtnMapper.setItemDelegate(_ButtonDelegate(self.pilotBtnMapper))
        self.ui.driverView.selectionModel().currentRowChanged.connect(
            self.pilotBtnMapper.setCurrentModelIndex)
        self.populated.connect(self.pilotBtnMapper.toFirst)
        self.ui.pilotBtn.toggled.connect(self.pilotBtnMapper.submit)

        self._specialColumnMapper.update(dict(
            laserpower=lambda column:
            self.powerBtnMapper.addMapping(self.ui.powerBtn, column),
            lasergate=lambda column:
            self.gateBtnMapper.addMapping(self.ui.gateBtn, column),
            pilotlaser=lambda column:
            self.pilotBtnMapper.addMapping(self.ui.pilotBtn, column),
        ))


class AmtronDaq(drv.Subsystem):

    """Instrument using the DAQ for input (temperature) and the CS400
    for output (laser power).  Output is controller by a software PID.

    """
    # connections:
    #    thermometer      pid           laser
    #    measure      ->  compute   ->  output
    def __init__(self, serial, daqline):
        super(AmtronDaq, self).__init__()
        self.pid = virtual.PidSubsystem(self, spmin=-100.0, spmax=1000.0)
        self.temperature = daq.Daq(daqline)
        self.temperature.voltage.ai._rfunc = partial(mul, 100)
        self.laser = amtron.CS400(serial)
        self.laser.control.control_mode.write(amtron.ControlMode.POWER)
        self.laser.command.laser_state.write(False)
        # Connections
        self.temperature.voltage.ai.signal.connect(self.pid.measure.write)
        self.temperature.voltage.ai.signal.connect(
            lambda value, node: self.pid.output.read(node))
        self.pid.output.signal.connect(self.laser.control.total_power.write)


class _VirtualCommand(object):

    def __init__(self):
        self.laser_state = False
        self.gate_state = False


class _VirtualInterface(object):

    def __init__(self):
        self.pilot_laser_state = False


class VirtualAmtronInstrument(virtual.VirtualInstrument):

    def __init__(self):
        super(VirtualAmtronInstrument, self).__init__()
        self.laser = drv.Subsystem(self)
        self.laser.command = drv.Subsystem(self.laser)
        self.laser.command.setProtocol(
            drv.ObjectWrapperProtocol(_VirtualCommand()))
        self.laser.command.laser_state = Cmd("laser_state")
        self.laser.command.gate_state = Cmd("gate_state")
        self.laser.interface = drv.Subsystem(self.laser)
        self.laser.interface.setProtocol(
            drv.ObjectWrapperProtocol(_VirtualInterface()))
        self.laser.interface.pilot_laser_state = Cmd("pilot_laser_state")


def createController():
    """Initialize controller."""
    config = ctrlr.Config("amtron", "CS400")
    if not config.nodes:
        config.nodes, config.names = (["ai0"], ["CS400"])
    if config.virtual:
        driver = VirtualAmtronInstrument()
        iface = AmtronController.virtualInstrumentController(config, driver)
    else:
        driver = AmtronDaq(drv.Serial(config.port), "Circat1")
        iface = AmtronController(config, driver)
        iface.addCommand(driver.temperature.voltage.ai, "temperature / C", poll=True, log=True)
        iface.addCommand(driver.pid.setpoint, "setpoint / C",
                         log=True, specialColumn="programmable")
        iface.addCommand(driver.laser.control.total_power, "power / W",
                         poll=True, log=True)
        iface.addCommand(driver.pid.proportional, "PID P", hide=True,
                         specialColumn="pidp")
        iface.addCommand(driver.pid.integral_time, "PID I", hide=True,
                         specialColumn="pidi")
        iface.addCommand(driver.pid.derivative_time, "PID D", hide=True,
                         specialColumn="pidd")
    iface.addCommand(driver.laser.command.laser_state, "power", hide=True,
                     poll=True, specialColumn="laserpower")
    iface.addCommand(driver.laser.command.gate_state, "gate", hide=True,
                     poll=True, specialColumn="lasergate")
    iface.addCommand(driver.laser.interface.pilot_laser_state, "pilot",
                     hide=True, poll=False, specialColumn="pilotlaser")
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
