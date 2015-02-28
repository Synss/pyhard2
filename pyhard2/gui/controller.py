"""Module with the default controller.

"""
import os
import time
from collections import defaultdict
from functools import partial
from zipfile import ZipFile
from StringIO import StringIO

import argparse
import yaml

from PyQt5 import QtWidgets, QtCore, QtGui
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal

from pyhard2 import __version__
from pyhard2.gui.model import DriverModel
from pyhard2.gui.driver import DriverWidget
from pyhard2.gui.monitor import MonitorWidget
from pyhard2.gui.programs import ProfileData, ProgramWidget, SingleShotProgram
from pyhard2.gui.widgets import Counter


__about__ = """
pyhard2 {version}, the free DDK written in Python.

Copyright (c) 2012-2015 Mathias Laurin.
Distributed under the GPLv3 License.
""".format(version=__version__)


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


class ControllerUi(QtWidgets.QMainWindow):

    """QMainWindow for the controllers."""

    def __init__(self, parent=None):
        super(ControllerUi, self).__init__(parent)
        centralWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(centralWidget)
        self.centralLayout = QtWidgets.QHBoxLayout(centralWidget)
        self._addDriverWidget()
        self._addMonitorWidget()
        self._addProgramWidget()

    @staticmethod
    def aboutBox(parent, checked):
        """Show about box."""
        QtWidgets.QMessageBox.about(parent, "About pyhard2", __about__)

    def _addDriverWidget(self, widget=DriverWidget):
        """Add default driver widget.  Derive `Controller` to change."""
        self.driverWidget = widget(self)
        self.centralLayout.addWidget(self.driverWidget)

    def _addMonitorWidget(self, widget=MonitorWidget):
        """Add default monitor widget.  Derive `Controller` to change."""
        self.monitorWidget = widget(self)
        self.centralLayout.addWidget(self.monitorWidget)
        self.monitorWidget.singleInstrumentCB.stateChanged.connect(
            self._setSingleInstrument)

    def _addProgramWidget(self, widget=ProgramWidget):
        """Add default program widget.  Derive `Controller` to change."""
        self.programWidget = widget(self)
        self.programWidget.startRequested.connect(self.startProgram)
        self.programWidget.stopRequested.connect(self.stopProgram)
        self.centralLayout.addWidget(self.programWidget)


class Controller(ControllerUi):

    """The default controller widget."""

    populated = Signal()

    def __init__(self, config, driver, parent=None):
        super(Controller, self).__init__(parent)
        self._config = config

        self.driverThread = QtCore.QThread(self)
        self.driver = driver
        self.driver.moveToThread(self.driverThread)
        self.driverThread.start()

        self.driverModel = DriverModel(self)

        self.driverWidget.setDriverModel(self.driverModel)
        self.monitorWidget.setDriverModel(self.driverModel)
        self.programWidget.setDriverModel(self.driverModel)

        self.programs = defaultdict(SingleShotProgram)
        self.refreshRate = Counter(self)
        self.driverWidget.verticalLayout.insertWidget(0, self.refreshRate)
        self.timer = self.refreshRate.timer
        self.setWindowTitle(config.title
                            + (" [virtual]" if config.virtual else ""))
        self.editorPrototype = defaultdict(QtWidgets.QDoubleSpinBox)

        selectionModel = self.driverWidget.driverView.selectionModel()
        selectionModel.currentRowChanged.connect(self._currentRowChanged)

        self._autoSaveTimer = QtCore.QTimer(self, singleShot=False,
                                            interval=600000)  # 10 min
        self.populated.connect(self._autoSaveTimer.start)
        self._autoSaveTimer.timeout.connect(self.autoSave)
        QtCore.QTimer.singleShot(0, self.autoSave)

        self._roleMapper = dict(
            program=self.setProgramColumn,
            pidp=self.setPidPColumn,
            pidi=self.setPidIColumn,
            pidd=self.setPidDColumn,)

        self.timer.timeout.connect(self.replot)
        self.timer.timeout.connect(self.refreshData)
        self.timer.timeout.connect(self.logData)

        self.populated.connect(self._setupWithModel)
        self.populated.connect(self.timer.start)
        self.populated.connect(self.driverWidget.pidBoxMapper.toFirst)

        for row, node in enumerate(self._config.nodes):
            try:
                name = self._config.names[row]
            except IndexError:
                name = "%s" % node
            self.addNode(node, name)

    @classmethod  # alt. ctor
    def virtualInstrumentController(cls, config, driver):
        """Initialize controller for the virtual instrument driver."""
        self = cls(config, driver)
        self.addCommand(driver.input.measure, u"measure", poll=True, log=True)
        self.addCommand(driver.pid.setpoint, u"setpoint", log=True,
                        role="program")
        self.addCommand(driver.output.output, u"output", poll=True, log=True)
        self.addCommand(driver.pid.proportional, u"PID P", hide=True,
                        role="pidp")
        self.addCommand(driver.pid.integral_time, u"PID I", hide=True,
                        role="pidi")
        self.addCommand(driver.pid.derivative_time, u"PID D", hide=True,
                        role="pidd")
        return self

    def _setupWithModel(self):
        self.driverWidget.populate()
        self.programWidget.populate()
        self.monitorWidget.populate()

    def _setSingleInstrument(self, state):
        selectionModel = self.driverView.selectionModel()
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
        path = os.path
        autoSaveFileName = path.join(QtGui.QDesktopServices.storageLocation(
            QtWidgets.QDesktopServices.DocumentsLocation),
            "pyhard2", time.strftime("%Y"), time.strftime("%m"),
            time.strftime("%Y%m%d.zip"))
        self.monitorWidget.autoSaveEdit.setText(autoSaveFileName)
        if not path.exists(path.dirname(autoSaveFileName)):
            os.makedirs(path.dirname(autoSaveFileName))
        return autoSaveFileName

    @Slot()
    def replot(self):
        """Update the monitor."""
        self.monitorWidget.draw()

    @Slot()
    def refreshData(self, force=False):
        """Request update to the `driverModel` from the hardware."""
        for item in self.driverModel:
            if item.isPolling() or force:
                item.queryData()

    @Slot()
    def logData(self):
        """Save data."""

    @Slot()
    def autoSave(self):
        """Export the data in the `monitor` to an archive."""
        return
        path = os.path
        with ZipFile(self.autoSaveFileName(), "a") as zipfile:
            for line in self.monitorWidget.axes.artists:
                csvfile = StringIO()
                line.data().exportAndTrim(csvfile)
                filename = path.join(
                    self.windowTitle(),
                    line.get_label(),
                    time.strftime("T%H%M%S")) + ".txt"
                zipfile.writestr(filename, csvfile.getvalue())

    def addCommand(self, command, label="",
                   hide=False, poll=False, log=False,
                   role=""):
        """Add `command` as a new column in the driver table.

        Parameters:
            hide (bool): Hide the column.
            poll (bool): Set the default polling state.
            log (bool): Set the default logging state.
            role {"program", "pidp", "pidi", "pidd"}:
                Connect the column to the relevant GUI elements.

        """
        column = self.driverModel.columnCount()
        self.driverModel.addCommand(command, label, poll, log)
        self.driverWidget.driverView.setColumnHidden(column, hide)
        if role:
            self._roleMapper[role.lower()](column)

    def addNode(self, node, label=""):
        """Add `node` as a new row in the driver table."""
        self.driverModel.addNode(node, label)

    def programColumn(self):
        """Return the index of the programmable column."""
        return self.programWidget.programColumn

    def setProgramColumn(self, column):
        """Set the programmable column to `column`."""
        self.programWidget.programColumn = column

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
        """Start program for item at (`row`, `programColumn`)."""
        if self.programColumn() is None:
            return

        def setInterval(dt):
            program.setInterval(1000 * dt)

        program = self.programs[row]
        # Connect program to GUI
        program.finished.connect(partial(self.stopProgram, row))
        program.setInterval(1000 * self.refreshRate.value())
        self.refreshRate.valueChanged.connect(setInterval)
        # Set (time, setpoint) profile
        program.setProfile(ProfileData.fromRootItem(
            self.programWidget.model.item(row, 0)))
        # Bind to item in driverModel
        driverItem = self.driverModel.item(
            row, self.programColumn())
        program.value.connect(partial(driverItem.setData))
        # Start
        program.start()

    def stopProgram(self, row):
        """Stop program for `row`."""
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
        self.driverThread.quit()
        self.driverThread.wait()
        event.accept()
