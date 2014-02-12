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


class AmtronController(ctrlr.SetpointController):

    def __init__(self, parent=None):
        super(AmtronController, self).__init__(parent)
        self.__initPowerBox()
        self._updateModel()

    def __initPowerBox(self):
        paneLayout = self._instrPane.layout()
        powerBoxLayout = QtGui.QHBoxLayout()
        paneLayout.addLayout(powerBoxLayout)
        self._powerBtn = QtGui.QPushButton(u"Power")
        self._powerBtn.setCheckable(True)
        self._gateBtn = QtGui.QPushButton(u"Gate")
        self._gateBtn.setCheckable(True)
        powerBoxLayout.addWidget(self._powerBtn)
        powerBoxLayout.addWidget(self._gateBtn)

        self._powerBoxMapper = QtGui.QDataWidgetMapper(self._instrTable)
        self._powerBoxMapper.setItemDelegate(
            _ButtonDelegate(self._powerBoxMapper))
        self._powerBoxMapper.setSubmitPolicy(self._powerBoxMapper.AutoSubmit)

    def _updateModel(self):
        model = self.instrumentTable().model()
        model.insertColumns(model.columnCount(), 2)
        powerColumn = model.columnCount() - 2
        gateColumn  = model.columnCount() - 1
        for column, name in (
                (powerColumn, u"power"),
                (gateColumn, u"gate")):
            model.setHorizontalHeaderItem(column, QtGui.QStandardItem(name))
            model.registerParameter(column, str(name))
            model.setPollingOnColumn(column)

        self._powerBoxMapper.setModel(model)
        self._instrTable.selectionModel().currentRowChanged.connect(
            self._powerBoxMapper.setCurrentModelIndex)
        for editor, column in (
                (self._powerBtn, powerColumn),
                (self._gateBtn, gateColumn)):
            self._powerBoxMapper.addMapping(editor, column)
            editor.toggled.connect(self._powerBoxMapper.submit)
        self._powerBoxMapper.toFirst()


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


class _VirtualAmtron(object):

    def __init__(self):
        self.laser_state = False
        self.gate_state = False
        self.total_power = 0.0
        self.measure = 0.0


class VirtualAmtronInstrument(virtual.VirtualInstrument):

    def __init__(self, socket, async=False):
        super(VirtualAmtronInstrument, self).__init__(socket, async)
        self.pid = virtual.PidSubsystem()
        protocol = drv.WrapperProtocol(_VirtualAmtron(), async=async)
        self.output = drv.Subsystem(protocol)
        for name in """ total_power
                    """.split():
            self.output.add_parameter_by_name(name, name)
        self.input = drv.Subsystem(protocol)
        for name in """ measure
                    """.split():
            self.input.add_parameter_by_name(name, name)
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


def createController(opts):
    """Register `xxx` and `yyy`."""

    iface = AmtronController()
    iface.setWindowTitle(u"Amtron CS400 controller")
    if not opts.config:
        opts.config = {"virtual": [dict(name="CS400", driver="virtual")]}
    if opts.virtual:
        iface.setWindowTitle(iface.windowTitle() + u" [virtual]")
    iface.addInstrumentClass(AmtronDaqInstrument, "CS400", mapper)
    iface.addInstrumentClass(VirtualAmtronInstrument, "virtual", mapper)
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
