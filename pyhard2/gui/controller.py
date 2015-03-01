"""Module with the default controller.

"""
import os
from datetime import datetime
from collections import defaultdict
from functools import partial

import argparse
import yaml

import numpy as np
from matplotlib.lines import Line2D

from PyQt5 import QtWidgets, QtCore, QtGui
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal

from pyhard2 import __version__
import pyhard2.db as db
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
            config.port = next(iter(section_.keys()))
            for __ in section_.values():
                for index, node_config in enumerate(__):
                    config.nodes.append(node_config.get("node", index))
                    config.names.append(node_config.get("name", "%s" % index))
    if not config.port:
        config.virtual = True
    return config


class ControllerUi(QtWidgets.QMainWindow):

    """QMainWindow for the controllers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        centralWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(centralWidget)
        self.centralLayout = QtWidgets.QHBoxLayout(centralWidget)
        self._addDriverWidget()
        self._addMonitorWidget()
        self._addProgramWidget()
        self.refreshRate = Counter(self)
        self.driverWidget.verticalLayout.insertWidget(0, self.refreshRate)
        self.timer = self.refreshRate.timer

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

    def __init__(self, config, driver, parent=None):
        super().__init__(parent)
        self._config = config

        if self._config.virtual:
            url = "sqlite:///"
        else:
            documents = QtGui.QDesktopServices.storageLocation(
                QtGui.QDesktopServices.DocumentsLocation)
            url = os.path.join(documents, "pyhard2.db")
        self._db = db.get_session(url)

        self.driverThread = QtCore.QThread(self)
        self.driver = driver
        self.driver.moveToThread(self.driverThread)
        self.driverThread.start()

        self.driverModel = DriverModel(self)
        self.driverWidget.setDriverModel(self.driverModel)
        self.monitorWidget.setDriverModel(self.driverModel)
        self.programWidget.setDriverModel(self.driverModel)

        self._monitorLines = {}

        self.programs = defaultdict(SingleShotProgram)
        self.setWindowTitle(config.title
                            + (" [virtual]" if config.virtual else ""))
        self.editorPrototype = defaultdict(QtWidgets.QDoubleSpinBox)

        selectionModel = self.driverWidget.driverView.selectionModel()
        selectionModel.currentRowChanged.connect(self._currentRowChanged)

        self._roleMapper = dict(
            program=self.setProgramColumn,
            pidp=self.setPidPColumn,
            pidi=self.setPidIColumn,
            pidd=self.setPidDColumn,)

        self.timer.timeout.connect(self._refreshData)
        self.timer.timeout.connect(self._refreshMonitor)

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
        self.addCommand(driver.input.measure, "measure")
        self.addCommand(driver.pid.setpoint, "setpoint", role="program")
        self.addCommand(driver.output.output, "output")
        self.addCommand(driver.pid.proportional, "PID P", hide=True,
                        role="pidp")
        self.addCommand(driver.pid.integral_time, "PID I", hide=True,
                        role="pidi")
        self.addCommand(driver.pid.derivative_time, "PID D", hide=True,
                        role="pidd")
        return self

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

    @Slot()
    def _refreshData(self, force=False):
        """Request update to the `driverModel` from the hardware."""
        for item in self.driverModel:
            if item.isPolling() or force:
                item.queryData()

    @Slot(QtGui.QStandardItem, object)
    def _logData(self, item, value):
        """Save data into database."""
        entry = db.LogTable(
            controller=self._config.title,
            node=item.node(),
            command=item.name(),
            timestamp=datetime.utcnow(),
            value=value,
        )
        self._db.add(entry)
        self._db.commit()

    def _refreshMonitor(self):
        q = self._db.query(db.LogTable).distinct(db.LogTable.command)
        for item in self.driverModel:
            if self.driverWidget.driverView.isColumnHidden(item.column()):
                continue
            node, command = item.node(), item.name()
            q = (self._db.query(db.LogTable)
                 .filter(db.LogTable.command == command)
                 .filter(db.LogTable.node == node))
            data = np.array([(timestamp, value)
                             for timestamp, value
                             in ((row.timestamp, row.value)
                                 for row in q.all())])
            line = self._monitorLines[(node, command)]
            line.set_data(data[:, 0], data[:, 1])
        self.monitorWidget.axes.relim()
        self.monitorWidget.axes.autoscale_view()
        self.monitorWidget.axes.figure.canvas.draw_idle()

    def addCommand(self, command, label="", hide=False, role=""):
        """Add `command` as a new column in the driver table.

        Parameters:
            hide (bool): Hide the column and disable polling.
            role {"program", "pidp", "pidi", "pidd"}:
                Connect the column to the relevant GUI elements.

        """
        column = self.driverModel.columnCount()
        self.driverModel.addCommand(command, label, poll=not hide)
        self.driverWidget.driverView.setColumnHidden(column, hide)
        if role:
            self._roleMapper[role.lower()](column)

    def addNode(self, node, label=""):
        """Add `node` as a new row in the driver table."""
        self.driverModel.addNode(node, label)
        self.programWidget.addNode(label)

    def populate(self):
        """Populate the driver table."""
        # Calls itemFromIndex to lazily create the items.
        for item in (
            self.driverModel.itemFromIndex(self.driverModel.index(row, column))
                for row in range(self.driverModel.rowCount())
                for column in range(self.driverModel.columnCount())):
            item.connectDriver()
            item.command().signal.connect(partial(self._logData, item))
            item.queryData()
            line = Line2D([], [])
            self._monitorLines[(item.node(), item.name())] = line
            self.monitorWidget.axes.add_line(line)
        self.timer.start()
        self.driverWidget.pidBoxMapper.toFirst()

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

    def __del__(self):
        self._db.close()

    def closeEvent(self, event):
        self.timer.stop()
        self.driverThread.quit()
        self.driverThread.wait()
        event.accept()
