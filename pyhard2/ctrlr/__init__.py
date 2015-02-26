# This file is part of pyhard2 - An object-oriented framework for the
# development of instrument drivers.

# Copyright (C) 2012-2014 Mathias Laurin, GPLv3


"""Qt4 graphical user interface for the controllers.

"""
import logging
logging.basicConfig()
from collections import defaultdict
import os as _os
import StringIO as _StringIO
import zipfile as _zipfile
from functools import partial as _partial
import time as _time

import argparse
import yaml

import sip as _sip
for _type in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    _sip.setapi(_type, 2)

from PyQt4 import QtCore, QtGui, uic
Qt = QtCore.Qt
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal

import pyhard2
from pyhard2.gui.driver import DriverModel, DriverWidget
from pyhard2.gui.monitor import MonitorWidget
from pyhard2.gui.programs import ProfileData, ProgramWidget, SingleShotProgram
import pyhard2.rsc


def Config(section, title="Controller",
           description="pyhard2 GUI configuration"):
    """Handle command line arguments and configuration files to
    initialize `Controllers`.

    Command line arguments:
        - ``-t``, ``--title``: The name of the controller.
        - ``-p``, ``--port``: The port where the hardware is connected.
        - ``-n``, ``--nodes``: A space-separated list of nodes at `port`.
        - ``-m``, ``--names``: A corresponding list of names for the `nodes`.
        - ``-v``, ``--virtual``: Load the virtual offline driver.
        - `file`: The path to a configuration file.

    Launching a controller from the command line with::

        python pyhard2/ctrlr/MODULE -p COM1 -n 1 2 3 -m first second third

    or by pointing to a file containing

    .. code-block:: yaml

        MODULE:
            COM1:
                - node: 1
                  name: first

                - node: 2
                  name: second

                - node: 3
                  name: third

    leads to the same result.

    Example:

        From the root directory of a working installation of `pyhard2`,
        the following line starts a virtual controller with three
        nodes::

            python pyhard2/ctrlr/pfeiffer -v -n 1 2 3 -m gauge1 gauge2

    """
    parser = argparse.ArgumentParser(description)
    parser.add_argument('-t', '--title', nargs="*",
                        default="%s %s" % (section.capitalize(), title))
    parser.add_argument('-p', '--port')
    parser.add_argument('-n', '--nodes', nargs="*", default=[])
    parser.add_argument('-m', '--names', nargs="*", default=[])
    parser.add_argument('-v', '--virtual', action="store_true")
    parser.add_argument('file', type=argparse.FileType("r"), nargs="?")
    parser.add_argument('config', nargs="*")
    config = parser.parse_args()
    if config.file:
        section_ = yaml.load(config.file).get(section)
        if section_:
            config.port = section_.iterkeys().next()
            for __ in section_.itervalues():
                for index, node_config in enumerate(__):
                    config.nodes.append(node_config.get("node", index))
                    config.names.append(node_config.get("name", u"%s" % index))
    if not config.port:
        config.virtual = True
    return config


class ScientificSpinBox(QtGui.QDoubleSpinBox):

    """QDoubleSpinBox with a scientific display."""

    def __init__(self, parent=None):
        super(ScientificSpinBox, self).__init__(parent)
        self.setMinimumWidth(self.fontMetrics().width("0.000e-00"))
        self.setDecimals(50)

    def textFromValue(self, value):
        """Return the formatted value."""
        return "%.2e" % value

    def valueFromText(self, text):
        """Return the text as a float."""
        return float(text)


class ControllerUi(QtGui.QMainWindow):

    """QMainWindow for the controllers.

    This class loads `uifile` if one is provided or defaults to the
    `ui/controller.ui` designer file and sets UI properties that are not
    accessible in designer.

    """
    def __init__(self, uifile=None):
        super(ControllerUi, self).__init__()
        try:
            self.ui = uic.loadUi(uifile, self)
        except IOError:
            uifile = QtCore.QFile(":/ui/controller.ui")
            uifile.open(QtCore.QFile.ReadOnly)
            self.ui = uic.loadUi(uifile, self)
            uifile.close()

        self.actionAbout_pyhard2.triggered.connect(
            _partial(ControllerUi.aboutBox, self))

    @staticmethod
    def aboutBox(parent, checked):
        QtGui.QMessageBox.about(parent, u"About pyhard2", u"\n".join((
            u"pyhard2 %s" % pyhard2.__version__,
            u"The free DDK written in Python."
            u"",
            u"Copyright (c) 2012-2014 Mathias Laurin.",
            u"Distributed under the GPLv3 License.")))


class Controller(QtCore.QObject):

    """Implement the behavior of the GUI.

    Methods:
        windowTitle()
        setWindowTitle(title)
            This property holds the window title (caption).
        show: Show the widget and its child widgets.
        close: Close the widget.

    """
    populated = Signal()

    def __init__(self, config, driver, uifile="", parent=None):
        super(Controller, self).__init__(parent)
        self._config = config
        self.ui = ControllerUi(uifile)
        self._addDriverWidget()
        self._addMonitorWidget()
        self._addProgramWidget()
        self.driverModel = DriverModel(driver)
        self.programs = defaultdict(SingleShotProgram)
        self.refreshRate = self.driverWidget.refreshRate
        self.timer = self.driverWidget.refreshRate.timer

        # UI methods
        self.windowTitle = self.ui.windowTitle
        self.setWindowTitle = self.ui.setWindowTitle
        self.show = self.ui.show
        self.close = self.ui.close

        title = config.title + (" [virtual]" if config.virtual else "")
        self.setWindowTitle(title)
        self.editorPrototype = defaultdict(QtGui.QDoubleSpinBox)

        self._autoSaveTimer = QtCore.QTimer(self, singleShot=False,
                                            interval=600000)  # 10 min
        self.populated.connect(self._autoSaveTimer.start)
        self._autoSaveTimer.timeout.connect(self.autoSave)
        QtCore.QTimer.singleShot(0, self.autoSave)

        self._specialColumnMapper = dict(
            programmable=self.setProgrammableColumn,
            pidp=self.setPidPColumn,
            pidi=self.setPidIColumn,
            pidd=self.setPidDColumn,)

        self.timer.timeout.connect(self.replot)
        self.timer.timeout.connect(self.refreshData)
        self.timer.timeout.connect(self.logData)

        self.populated.connect(self._setupWithConfig)
        self.populated.connect(self.timer.start)
        self.populated.connect(self.driverWidget.pidBoxMapper.toFirst)

        for row, node in enumerate(self._config.nodes):
            try:
                name = self._config.names[row]
            except IndexError:
                name = "%s" % node
            self.addNode(node, name)

    def _addDriverWidget(self, widget=DriverWidget):
        self.driverWidget = widget(self.ui)
        self.ui.centralWidget().layout().addWidget(self.driverWidget)

    def _addMonitorWidget(self, widget=MonitorWidget):
        self.monitorWidget = widget(self.ui)
        self.ui.centralWidget().layout().addWidget(self.monitorWidget)
        self.monitorWidget.singleInstrumentCB.stateChanged.connect(
            self._setSingleInstrument)

    def _addProgramWidget(self, widget=ProgramWidget):
        self.programWidget = widget(self.ui)
        self.programWidget.startRequested.connect(self.startProgram)
        self.programWidget.stopRequested.connect(self.stopProgram)
        self.ui.centralWidget().layout().addWidget(self.programWidget)

    def _setupWithConfig(self):
        self.driverWidget.setDriverModel(self.driverModel)
        selectionModel = self.driverWidget.driverView.selectionModel()
        selectionModel.currentRowChanged.connect(self._currentRowChanged)
        self.programWidget.setDriverModel(self.driverModel)
        self.monitorWidget.setDriverModel(self.driverModel)

    def _setSingleInstrument(self, state):
        selectionModel = self.ui.driverView.selectionModel()
        selection = selectionModel.selectedRows()
        if not selection:
            return
        row = selection.pop().row()
        self.monitorWidget.setSingleInstrument(row, state)

    def _currentRowChanged(self, current, previous):
        self.driverWidget.pidBoxMapper.setCurrentModelIndex(current)
        self.monitorWidget.setCurrentRow(current.row(), previous.row())
        self.programWidget.setProgramTableRoot(current.row())

    def autoSaveFileName(self):
        path = _os.path
        autoSaveFileName = path.join(QtGui.QDesktopServices.storageLocation(
            QtGui.QDesktopServices.DocumentsLocation),
            "pyhard2", _time.strftime("%Y"), _time.strftime("%m"),
            _time.strftime("%Y%m%d.zip"))
        self.monitorWidget.autoSaveEdit.setText(autoSaveFileName)
        if not path.exists(path.dirname(autoSaveFileName)):
            _os.makedirs(path.dirname(autoSaveFileName))
        return autoSaveFileName

    @Slot()
    def replot(self):
        self.monitorWidget.draw()

    @Slot()
    def refreshData(self, force=False):
        for item in self.driverModel:
            if item.isPolling() or force:
                item.queryData()

    @Slot()
    def logData(self):
        for item in self.driverModel:
            if item.isLogging():
                self.monitorWidget.data[item].append(item.data())

    @Slot()
    def autoSave(self):
        """Export the data in the `monitor` to an archive."""
        path = _os.path
        with _zipfile.ZipFile(self.autoSaveFileName(), "a") as zipfile:
            for curve in self.monitorWidget.monitor.itemList():
                csvfile = _StringIO.StringIO()
                curve.data().exportAndTrim(csvfile)
                filename = path.join(
                    self.windowTitle(),
                    curve.title().text(),
                    _time.strftime("T%H%M%S")) + ".txt"
                zipfile.writestr(filename, csvfile.getvalue())

    @classmethod  # alt. ctor
    def virtualInstrumentController(cls, config, driver):
        """Initialize controller for the virtual instrument driver."""
        self = cls(config, driver)
        self.addCommand(driver.input.measure, u"measure", poll=True, log=True)
        self.addCommand(driver.pid.setpoint, u"setpoint", log=True,
                        specialColumn="programmable")
        self.addCommand(driver.output.output, u"output", poll=True, log=True)
        self.addCommand(driver.pid.proportional, u"PID P", hide=True,
                        specialColumn="pidp")
        self.addCommand(driver.pid.integral_time, u"PID I", hide=True,
                        specialColumn="pidi")
        self.addCommand(driver.pid.derivative_time, u"PID D", hide=True,
                        specialColumn="pidd")
        return self

    def addCommand(self, command, label="",
                   hide=False, poll=False, log=False,
                   specialColumn=""):
        """Add `command` as a new column in the driver table.

        Parameters:
            hide (bool): Hide the column.
            poll (bool): Set the default polling state.
            log (bool): Set the default logging state.
            specialColumn {"programmable", "pidp", "pidi", "pidd"}:
                Connect the column to the relevant GUI elements.

        """
        column = self.driverModel.columnCount()
        self.driverModel.addCommand(command, label, poll, log)
        self.driverWidget.driverView.setColumnHidden(column, hide)
        if specialColumn:
            self._specialColumnMapper[specialColumn.lower()](column)

    def addNode(self, node, label=""):
        """Add `node` as a new row in the driver table."""
        self.driverModel.addNode(node, label)

    def programmableColumn(self):
        """Return the index of the programmable column."""
        return self.programWidget.programmableColumn

    def setProgrammableColumn(self, column):
        """Set the programmable column to `column`."""
        self.programWidget.programmableColumn = column

    def setPidPColumn(self, column):
        """Set the pid P column to `column`."""
        self.driverWidget.mapPEditor(column)

    def setPidIColumn(self, column):
        """Set the pid I column to `column`."""
        self.driverWidget.mapIEditor(column)

    def setPidDColumn(self, column):
        """Set the pid D column to `column`."""
        self.driverWidget.mapDEditor(column)

    def startProgram(self, row):
        """Start program for item at (`row`, `programmableColumn`)."""
        if self.programmableColumn() is None:
            return

        def setInterval(dt):
            program.setInterval(1000 * dt)

        program = self.programs[row]
        # Connect program to GUI
        program.finished.connect(_partial(self.stopProgram, row))
        program.setInterval(1000 * self.refreshRate.value())
        self.refreshRate.valueChanged.connect(setInterval)
        # Set (time, setpoint) profile
        program.setProfile(ProfileData.fromRootItem(
            self.programWidget.model.item(row, 0)))
        # Bind to item in driverModel
        driverItem = self.driverModel.item(
            row, self.programmableColumn())
        program.value.connect(_partial(driverItem.setData))
        # Start
        program.start()

    def stopProgram(self, row):
        try:
            program = self.programs.pop(row)
        except KeyError:
            pass
        else:
            program.stop()

    def populate(self):
        """Populate the driver table."""
        self.driverModel.populate()
        self.populated.emit()

    def closeEvent(self, event):
        self.timer.stop()
        self._autoSaveTimer.stop()
        self.autoSave()
        super(Controller, self).closeEvent(event)
