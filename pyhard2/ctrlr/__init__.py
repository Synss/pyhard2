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
from pyhard2.gui.delegates import DoubleSpinBoxDelegate
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


class ItemRangedSpinBoxDelegate(DoubleSpinBoxDelegate):

    """Item delegate for editing models in a spin box.

    Every property of the spin box can be set on the delegate with the
    methods from QDoubleSpinBox.

    The minimum and maximum properties are set from the item to be
    edited.

    Inherits :class:`DoubleSpinBoxDelegate`.

    """
    def __init__(self, spinBox=None, parent=None):
        super(ItemRangedSpinBoxDelegate, self).__init__(spinBox, parent)

    def createEditor(self, parent, option, index):
        """Return a QDoubleSpinBox.

        - The `minimum` property of the spin box is set to
          `item.minimum()` if this value has been set.
        - The `maximum` property of the spin box is set to
          `item.maximum()` if this value has been set.
        """
        spinBox = super(ItemRangedSpinBoxDelegate, self).createEditor(
            parent, option, index)
        item = index.model().itemFromIndex(index)
        minimum, maximum = item.minimum(), item.maximum()
        if minimum is not None:
            spinBox.setMinimum(minimum)
        if maximum is not None:
            spinBox.setMaximum(maximum)
        return spinBox


class HorizontalHeaderItem(QtGui.QStandardItem):

    """Horizontal header item for the driver view."""

    CommandRole = Qt.UserRole + 1

    def __init__(self, text=""):
        super(HorizontalHeaderItem, self).__init__(text)
        self._defaultPollingState = False
        self._defaultLoggingState = False

    def type(self):
        """Return `QStandardItem.UserType`."""
        return self.UserType

    def clone(self):
        """Reimplemented from `QStandardItem`."""
        return self.__class__()

    def command(self):
        """Return the command for this column."""
        return self.data(role=HorizontalHeaderItem.CommandRole)

    def setCommand(self, command):
        """Set the command for this column to `command`."""
        self.setData(command, role=HorizontalHeaderItem.CommandRole)

    def defaultPollingState(self):
        """Return True if the column defaults to polling;
        otherwise return False."""
        return self._defaultPollingState is True

    def setDefaultPollingState(self, state):
        """Set the default polling state for this column to `state`."""
        self._defaultPollingState = state

    def defaultLoggingState(self):
        """Return True if the column defaults to logging;
        otherwise return False."""
        return self._defaultLoggingState is True

    def setDefaultLoggingState(self, state):
        """Set the default logging state for this column to `state`."""
        self._defaultLoggingState = state


class VerticalHeaderItem(QtGui.QStandardItem):

    """Item to use in vertical header of the driver model."""

    NodeRole = Qt.UserRole + 1

    def __init__(self, text=""):
        super(VerticalHeaderItem, self).__init__(text)

    def type(self):
        """Return QtGui.QStandardItem.UserType."""
        return self.UserType

    def clone(self):
        """Reimplemented from :class:`QtGui.QStandardItem`."""
        return self.__class__()

    def node(self):
        """Return the node for this row."""
        return self.data(role=VerticalHeaderItem.NodeRole)

    def setNode(self, node):
        """Set the node for this row to `node`."""
        self.setData(node, role=VerticalHeaderItem.NodeRole)


class SignalProxy(QtCore.QObject):  # Obsolete in Qt5
    """Proxy class for Qt4 signals.

    SignalProxy can be used in place of a Signal in classes that do not
    inherit QObject.

    """
    signal = Signal(object)

    def __init__(self, parent=None):
        super(SignalProxy, self).__init__(parent)
        self.connect = self.signal.connect
        self.disconnect = self.signal.disconnect
        self.emit = self.signal.emit


PollingRole = Qt.UserRole + 2
LoggingRole = Qt.UserRole + 3


class DriverItem(QtGui.QStandardItem):

    """`QStandardItem` handling communication with the driver."""

    def __init__(self):
        super(DriverItem, self).__init__()
        self._signal = SignalProxy()  # Used to write to the driver.

    def type(self):
        """Return QtGui.QStandardItem.UserType."""
        return self.UserType

    def clone(self):
        """Reimplemented from `QStandardItem`."""
        return self.__class__()

    def _horizontalHeaderItem(self):
        """Return the HorizontalHeaderItem for this item's column."""
        return self.model().horizontalHeaderItem(self.column())

    def _verticalHeaderItem(self):
        """Return the VerticalHeaderItem for this item's row."""
        return self.model().verticalHeaderItem(self.row())

    def isPolling(self):
        """Return True if polling is enabled for this item;
        otherwise return False."""
        state = self.data(role=PollingRole)
        return (self._horizontalHeaderItem().defaultPollingState()
                if state is None else state)

    def setPolling(self, state):
        """Set polling to `state` for this item."""
        self.setData(state, role=PollingRole)

    def isLogging(self):
        """Return True if logging is enabled for this item;
        otherwise return False."""
        state = self.data(role=LoggingRole)
        return (self._horizontalHeaderItem().defaultLoggingState()
                if state is None else state)

    def setLogging(self, state):
        """Set logging to `state` for this item."""
        self.setData(state, role=LoggingRole)

    def command(self):
        """Return the `Command` object for this column."""
        return self._horizontalHeaderItem().command()

    def node(self):
        """Return the `node` for this row, if any."""
        return self._verticalHeaderItem().node()

    def minimum(self):
        """Return the minimum value for this item.

        The value is read in the driver."""
        return self.command().minimum

    def maximum(self):
        """Return the maximum value for this item.

        The value is read in the driver"""
        return self.command().maximum

    def isReadOnly(self):
        """Return the read only value for this item.

        The value is read in the driver."""
        return self.command().access == "Access.RO"

    def queryData(self):
        """Request reading data in the driver.

        Note:
            - The query is constructed from the `Command` set on this
              item's column and the `node` (if any) set for this item's
              row.
            - If the driver raises a `HardwareError`, the error is
              logged but execution continues.

        """
        try:
            self.command().read(self.node())
        except drv.HardwareError as e:
            logging.getLogger(__name__).error(
                "%s:%s:%s" % (self.command().reader,
                              self.node(),
                              e))

    def _connectDriver(self):
        """Connect the `Command` to this item using Qt4 signals and slots.

        The read only flag is also set according to the `Command`.

        """
        def displayData(data, node):
            if node == self.node():
                self.setData(data, role=Qt.DisplayRole)

        def writeData(data):
            if not self.isReadOnly():
                self.command().write(data, self.node())

        self.setEditable(not self.isReadOnly())
        # getter
        self.command().signal.connect(displayData, type=Qt.QueuedConnection)
        # setter
        self._signal.connect(writeData, type=Qt.QueuedConnection)

    def data(self, role=Qt.DisplayRole):
        """Default to Qt.DisplayRole."""
        return super(DriverItem, self).data(role)

    def setData(self, value, role=Qt.EditRole):
        """Default to Qt.EditRole."""
        super(DriverItem, self).setData(value, role)
        if role == Qt.EditRole and not self.isReadOnly():
            self._signal.emit(value)


class DriverModel(QtGui.QStandardItemModel):

    """Model to handle the driver."""

    def __init__(self, driver, parent=None):
        super(DriverModel, self).__init__(parent)
        self._thread = QtCore.QThread(self)
        self._driver = driver
        self._driver.moveToThread(self._thread)
        self._thread.start()
        self.setItemPrototype(DriverItem())

    def __repr__(self):
        return "%s(driver=%r, parent=%r)" % (
            self.__class__.__name__, self._driver, self.parent())

    def __iter__(self):
        """Iterate on items."""
        return (self.item(row, column)
                for row in range(self.rowCount())
                for column in range(self.columnCount()))

    def driver(self):
        """Return the driver for this model."""
        return self._driver

    def node(self, row):
        """Return node for `row`, if any."""
        return self.verticalHeaderItem(row).node()

    def addNode(self, node, label=""):
        """Add `node` as a new row with `label`."""
        row = self.rowCount()
        if not label:
            label = node if node is not None else "%i" % row
        headerItem = VerticalHeaderItem(label)
        headerItem.setNode(node)
        self.setVerticalHeaderItem(row, headerItem)

    def addCommand(self, command, label="", poll=False, log=False):
        """Add `command` as a new column with `label`."""
        column = self.columnCount()
        item = HorizontalHeaderItem(label if label else "C%i" % column)
        item.setCommand(command)
        item.setDefaultPollingState(poll)
        item.setDefaultLoggingState(log)
        self.setHorizontalHeaderItem(column, item)

    def populate(self):
        """Fill the model with `DriverItem`."""
        for item in (self.itemFromIndex(self.index(row, column))
                     for row in range(self.rowCount())
                     for column in range(self.columnCount())):
            item._connectDriver()
            item.queryData()

    def closeEvent(self, event):
        """Let the driver thread exit cleanly."""
        self._thread.quit()
        self._thread.wait()
        event.accept()


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

        horizontalHeader = self.driverView.horizontalHeader()
        horizontalHeader.setResizeMode(QtGui.QHeaderView.Stretch)
        horizontalHeader.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        verticalHeader = self.driverView.verticalHeader()
        verticalHeader.setResizeMode(QtGui.QHeaderView.ResizeToContents)

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
        isColumnHidden: Return True if the given `column` is hidden;
            otherwise return False.
        setColumnHidden: if `hide` is True, the given `column` will be
            hidden; otherwise it will be shown.

    """
    populated = Signal()

    def __init__(self, config, driver, uifile="", parent=None):
        super(Controller, self).__init__(parent)
        self._config = config
        self.ui = ControllerUi(uifile)
        self._addMonitorWidget()
        self._addProgramWidget()
        self.programs = defaultdict(SingleShotProgram)

        # UI methods
        self.windowTitle = self.ui.windowTitle
        self.setWindowTitle = self.ui.setWindowTitle
        self.show = self.ui.show
        self.close = self.ui.close
        self.setColumnHidden = self.ui.driverView.setColumnHidden
        self.isColumnHidden = self.ui.driverView.isColumnHidden

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

        self._driverModel = DriverModel(driver, self)
        self.populated.connect(self._setupWithConfig)
        self.ui.driverView.setModel(self._driverModel)

        self.ui.driverView.selectionModel().currentRowChanged.connect(
            self._currentRowChanged)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.replot)
        self.timer.setInterval(self.ui.refreshRateEditor.value() * 1000)
        self.timer.timeout.connect(self.refreshData)
        self.timer.timeout.connect(self.logData)
        self.ui.refreshRateEditor.valueChanged.connect(
            lambda dt: self.timer.setInterval(1000 * dt))
        self.populated.connect(self.timer.start)

        self.ui.driverView.setItemDelegate(
            ItemRangedSpinBoxDelegate(parent=self.ui.driverView))

        self.pidBoxMapper = QtGui.QDataWidgetMapper(self.ui.pidBox)
        self.pidBoxMapper.setModel(self._driverModel)
        self.pidBoxMapper.setSubmitPolicy(QtGui.QDataWidgetMapper.AutoSubmit)
        self.pidBoxMapper.setItemDelegate(
            ItemRangedSpinBoxDelegate(parent=self.pidBoxMapper))
        self.populated.connect(self.pidBoxMapper.toFirst)

        self.ui.driverView.customContextMenuRequested.connect(
            self.on_instrumentsTable_customContextMenuRequested)

        for row, node in enumerate(self._config.nodes):
            try:
                name = self._config.names[row]
            except IndexError:
                name = "%s" % node
            self.addNode(node, name)

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
        self.programWidget.setDriverModel(self._driverModel)
        self.monitorWidget.setDriverModel(self._driverModel)

    def _setSingleInstrument(self, state):
        selectionModel = self.ui.driverView.selectionModel()
        selection = selectionModel.selectedRows()
        if not selection:
            return
        row = selection.pop().row()
        self.monitorWidget.setSingleInstrument(row, state)

    def _currentRowChanged(self, current, previous):
        self.pidBoxMapper.setCurrentModelIndex(current)
        self.monitorWidget.setCurrentRow(current.row(), previous.row())
        self.programWidget.setProgramTableRoot(current.row())

    def on_instrumentsTable_customContextMenuRequested(self, pos):
        column = self.ui.driverView.columnAt(pos.x())
        row = self.ui.driverView.rowAt(pos.y())
        item = self._driverModel.item(row, column)
        rightClickMenu = QtGui.QMenu(self.ui.driverView)
        rightClickMenu.addActions(
            [QtGui.QAction(
                "Polling", self, checkable=True,
                checked=item.isPolling(), triggered=item.setPolling),
             QtGui.QAction(
                 "Logging", self, checkable=True,
                 checked=item.isLogging(), triggered=item.setLogging)
             ])
        rightClickMenu.exec_(self.ui.driverView.viewport()
                             .mapToGlobal(pos))

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
        for item in self._driverModel:
            if item.isPolling() or force:
                item.queryData()

    @Slot()
    def logData(self):
        for item in self._driverModel:
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
        column = self._driverModel.columnCount()
        self._driverModel.addCommand(command, label, poll, log)
        self.setColumnHidden(column, hide)
        if specialColumn:
            self._specialColumnMapper[specialColumn.lower()](column)

    def addNode(self, node, label=""):
        """Add `node` as a new row in the driver table."""
        self._driverModel.addNode(node, label)

    def programmableColumn(self):
        """Return the index of the programmable column."""
        return self.programWidget.programmableColumn

    def setProgrammableColumn(self, column):
        """Set the programmable column to `column`."""
        self.programWidget.programmableColumn = column

    def setPidPColumn(self, column):
        """Set the pid P column to `column`."""
        self.pidBoxMapper.addMapping(self.ui.pEditor, column)

    def setPidIColumn(self, column):
        """Set the pid I column to `column`."""
        self.pidBoxMapper.addMapping(self.ui.iEditor, column)

    def setPidDColumn(self, column):
        """Set the pid D column to `column`."""
        self.pidBoxMapper.addMapping(self.ui.dEditor, column)

    def startProgram(self, row):
        """Start program for item at (`row`, `programmableColumn`)."""
        if self.programmableColumn() is None:
            return

        def setInterval(dt):
            program.setInterval(1000 * dt)

        program = self.programs[row]
        # Connect program to GUI
        program.finished.connect(_partial(self.stopProgram, row))
        program.setInterval(1000 * self.ui.refreshRateEditor.value())
        self.ui.refreshRateEditor.valueChanged.connect(setInterval)
        # Set (time, setpoint) profile
        program.setProfile(ProfileData.fromRootItem(
            self.programWidget.model.item(row, 0)))
        # Bind to item in driverModel
        driverItem = self._driverModel.item(row, self.programmableColumn())
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
        self._driverModel.populate()
        self.populated.emit()

    def closeEvent(self, event):
        self.timer.stop()
        self._autoSaveTimer.stop()
        self.autoSave()
        super(Controller, self).closeEvent(event)
