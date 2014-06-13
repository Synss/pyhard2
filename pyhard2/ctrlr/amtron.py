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
import pyhard2.driver as drv
import pyhard2.driver.virtual as virtual
import pyhard2.driver.amtron as amtron
import pyhard2.driver.daq as daq


class _ButtonDelegate(QtGui.QAbstractItemDelegate):

    def __init__(self, parent=None):
        super(_ButtonDelegate, self).__init__(parent)

    def setEditorData(self, editor, index):
        if not index.isValid(): return
        editor.setChecked(index.data())

    def setModelData(self, editor, model, index):
        if not index.isValid(): return
        model.setData(index, editor.isChecked())


class PowerSwitchWidget(QtGui.QWidget):

    def __init__(self, title, parent=None):
        super(PowerSwitchWidget, self).__init__(parent)
        self.title = title
        self.__setupUI()

    def __setupUI(self):
        self.powerBtn = QtGui.QPushButton(u"Power")
        self.gateBtn = QtGui.QPushButton(u"Gate")

        self.powerBtn.setCheckable(True)
        self.gateBtn.setCheckable(True)

        self.layout = QtGui.QHBoxLayout(self)
        self.layout.addWidget(self.powerBtn)
        self.layout.addWidget(self.gateBtn)


class AmtronController(ctrlr.SetpointController):

    def __init__(self, parent=None):
        super(AmtronController, self).__init__(parent)
        self.__setupUI()

        model = self.instrumentTable().model()
        model.insertColumns(model.columnCount(), 2)
        powerColumn = model.columnCount() - 2
        gateColumn = model.columnCount() -1
        for column, name in (
                (powerColumn, u"power"),
                (gateColumn, u"gate")):
            model.setHorizontalHeaderItem(column, QtGui.QStandardItem(name))
            model.registerParameter(column, str(name))
            model.setPollingOnColumn(column)

        self.powerMapper = QtGui.QDataWidgetMapper(self)
        self.powerMapper.setItemDelegate(
            _ButtonDelegate(self.powerMapper))
        self.powerMapper.setModel(model)

        self._instrPanel.table.selectionModel().currentRowChanged.connect(
            self.powerMapper.setCurrentModelIndex)
        for editor, column in (
                (self.powerSwitches.powerBtn, powerColumn),
                (self.powerSwitches.gateBtn, gateColumn)):
            self.powerMapper.addMapping(editor, column)
            editor.toggled.connect(self.powerMapper.submit)

        model.configLoaded.connect(self.powerMapper.toFirst)

    def __setupUI(self):
        self.powerSwitches = PowerSwitchWidget("power", self)
        self._instrPanel.layout.addWidget(self.powerSwitches)


def scale(factor):
    def _scale(x):
        return factor * x
    return _scale


class AmtronDaqInstrument(drv.Instrument):

    """
    Instrument using the DAQ for input (temperature) and the CS400 for
    output (laser power).  Output is controller by a PID.

    """
    # connections:
    #    thermometer      pid           laser
    #    measure      ->  compute   ->  output
    def __init__(self, serial, daqline, async=False):
        super(AmtronDaqInstrument, self).__init__(serial, async)
        self.pid = virtual.PidSubsystem(spmin=-100.0, spmax=1000.0)
        self.__input = daq.AiInstrument(
            daq.AiSocket(daqline, name="laser_temp", terminal="RSE"),
            scale(100.0)
        )
        self.__output = amtron.CS400(serial)
        self.__output.control.control_mode = amtron.ControlMode.POWER
        self.__output.command.laser_state = False

        self.input = self.__input.main
        self.output = self.__output.control
        self.command = self.__output.command

        self.input.measure_signal().connect(self.pid.compute_output)
        self.pid.output.connect(self.output.set_total_power)


class _VirtualCommand(object):

    def __init__(self):
        self.laser_state = False
        self.gate_state = False


class VirtualAmtronInstrument(virtual.VirtualInstrument):

    def __init__(self, socket, async=False):
        super(VirtualAmtronInstrument, self).__init__(socket, async)
        protocol = drv.WrapperProtocol(_VirtualCommand(), async=async)
        self.command = drv.Subsystem(protocol)
        for name in """ laser_state
                        gate_state
                    """.split():
            self.command.add_parameter_by_name(name, name)


mapper = dict(
    setpoint="pid.setpoint",
    pid_gain="pid.proportional",
    pid_integral="pid.integral_time",
    pid_derivative="pid.derivative_time",
    output="output.total_power",
    measure="input.measure",
    power="command.laser_state",
    gate="command.gate_state",
)


virtual_mapper = dict(virtual.virtual_mapper)
virtual_mapper.update(dict(
    power="command.laser_state",
    gate="command.gate_state"))


def createController(opts):
    """Register `xxx` and `yyy`."""

    iface = AmtronController()
    iface.setWindowTitle(u"Amtron CS400 controller")
    if not opts.config:
        opts.config = {"virtual": [dict(name="CS400", driver="virtual")]}
    if opts.virtual:
        iface.setWindowTitle(iface.windowTitle() + u" [virtual]")
    iface.addInstrumentClass(AmtronDaqInstrument, "CS400", mapper)
    iface.addInstrumentClass(VirtualAmtronInstrument, "virtual",
                             virtual_mapper)
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
