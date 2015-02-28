"""Module with the stock programs and the default `ProgramWidget`.

"""
import numpy as np

from PyQt5 import QtWidgets, QtCore, QtGui
Qt = QtCore.Qt
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal

from pyhard2 import pid
import pyhard2.rsc
from pyhard2.gui.delegates import DoubleSpinBoxDelegate
from pyhard2.gui.selection import ItemSelectionModel
from pyhard2.gui.mpl import MplWidget, Line


class SingleShotProgram(QtCore.QObject):

    """Program that sends new values at predefined times.

    Note:
        The program has its own timer so that the events will fire
        precisely at the given times.

    Attributes:
        started: The signal is emitted when the program starts.
        finished: The signal is emitted when the program has finished
            executing.
        value: The signal is emitted with the value generated by the
            program.

    Methods:
        interval()
        setInterval(msec)
            This property holds the timeout interval in milliseconds.

    """
    started = Signal()
    finished = Signal()
    value = Signal(object)

    def __init__(self):
        super(SingleShotProgram, self).__init__()
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._shoot)
        self._running = False
        self._profile = None
        self._index = -1
        # methods:
        self.setInterval = self._timer.setInterval
        self.interval = self._timer.interval

    def profile(self):
        """Return the profile."""
        return self._profile

    def setProfile(self, profile):
        """Set the profile to `profile`."""
        self._profile = profile

    def isRunning(self):
        """Returns whether the program is running."""
        return self._running

    @property
    def _dt(self):
        """Difference between the current time and the next time."""
        return self._profile.x(self._index + 1) - self._profile.x(self._index)

    @property
    def _dv(self):
        """Difference between the current value and the next value."""
        return self._profile.y(self._index + 1) - self._profile.y(self._index)

    @Slot()
    def start(self):
        """Start or restart the program."""
        if self._running:
            # restart
            self.stop()
        self._running = True
        self.started.emit()
        self._shoot()

    @Slot()
    def stop(self):
        """Stop the program."""
        if not self._running:
            # ignore
            return
        self._running = False
        self._timer.stop()
        self._index = -1
        self.finished.emit()

    @Slot()
    def _shoot(self):
        """Emit a value if it exists or terminate the program."""
        self._index += 1
        try:
            self.value.emit(self._profile.y(self._index))
        except IndexError:
            # Current value does not exist.
            self.stop()
        try:
            # relative time
            dt = self._dt
        except IndexError:
            # Next value does not exist.
            self.stop()
        else:
            self._timer.start(1000 * dt)  # msec


class SetpointRampProgram(SingleShotProgram):

    """Program that performs setpoint ramps."""

    def __init__(self):
        super(SetpointRampProgram, self).__init__()
        self._ramp = None
        self._timer.setSingleShot(False)
        self.started.connect(self._timer.start)
        self.finished.connect(self._timer.stop)

    def setProfile(self, profile):
        """Set the profile to `profile`."""
        super(SetpointRampProgram, self).setProfile(profile)
        self._ramp = pid.Profile(list(self._profile)).ramp()

    @Slot()
    def _shoot(self):
        """Emit a new value if it exists or terminate the program."""
        try:
            self.value.emit(next(self._ramp))
        except StopIteration:
            try:
                self.value.emit(self._profile.y(-1))
            except IndexError:
                # Ignore error: we are stopping anyway.
                pass
            self.stop()


class ProfileData(object):

    """Helper to use 2 x `n` arrays to monitor data."""

    X, Y = range(2)

    def __init__(self, array):
        self.array = array

    @classmethod
    def fromRootItem(cls, item):

        """Make a 2 x `n` array from the children of `item`."""

        def unroll(column):
            return [data for data
                    in (item.child(row, column).data(Qt.DisplayRole)
                        for row in range(item.rowCount()))
                    if data is not None]

        x, y = unroll(0), unroll(1)
        length = min(len(x), len(y))
        return cls(np.array((x[:length], y[:length])))

    def x(self, i):
        """Return `x` value at index `i`."""
        return self.array[ProfileData.X][i].item()

    def y(self, i):
        """Return `y` value at index `i`."""
        return self.array[ProfileData.Y][i].item()


class ProgramWidgetUi(QtWidgets.QWidget):

    """The default UI for the program widget."""

    def __init__(self, parent=None):
        super(ProgramWidgetUi, self).__init__(parent)
        sp = QtWidgets.QSizePolicy
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.setSizePolicy(sp.Fixed, sp.Expanding)
        self.updateGeometry()
        self.toolBar = QtWidgets.QToolBar(self)
        self.verticalLayout.addWidget(self.toolBar)
        self.programView = QtWidgets.QTableView(self)
        sizePolicy = QtWidgets.QSizePolicy(sp.Expanding, sp.Expanding)
        sizePolicy.setVerticalStretch(3)
        self.programView.setSizePolicy(sizePolicy)
        self.programView.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.programView.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch)
        self.programView.verticalHeader().setVisible(False)
        self.programView.verticalHeader().setDefaultSectionSize(20)
        self.verticalLayout.addWidget(self.programView)
        self.previewPlot = MplWidget(self)
        sizePolicy = QtWidgets.QSizePolicy(sp.Expanding, sp.Expanding)
        sizePolicy.setVerticalStretch(2)
        self.previewPlot.setSizePolicy(sizePolicy)
        self.verticalLayout.addWidget(self.previewPlot)
        self.axes = self.previewPlot.figure.add_subplot(111)

    def scaleToArtists(self, artists):
        if not artists:
            return
        # Scale
        xmin, xmax = self.axes.get_xbound()
        ymin, ymax = self.axes.get_ybound()
        data = np.hstack(artist.get_data() for artist in artists)
        xdata_min, ydata_min = data.min(axis=1)
        xdata_max, ydata_max = data.max(axis=1)
        if xdata_min < xmin or xdata_max > xmax:
            self.axes.set_xbound(xdata_min * 0.8, xdata_max * 1.2)
        elif ydata_min < ymin or ydata_max > ymax:
            self.axes.set_ybound(ydata_min * 0.8, ydata_max * 1.2)


class ProgramWidget(ProgramWidgetUi):

    """The default widget for the program widget.

    .. image:: img/programs.png

    """
    startRequested = Signal(int)
    stopRequested = Signal(int)

    def __init__(self, parent=None):
        super(ProgramWidget, self).__init__(parent)
        self.driverModel = None
        self.programColumn = None
        self._previewPlotItems = []  # defeat GC

        self.model = QtGui.QStandardItemModel(self)
        self.programView.setModel(self.model)

        timeColumnDelegate = DoubleSpinBoxDelegate(parent=self.programView)
        timeColumnDelegate.setRange(0.0, 604800.0)  # 7 days
        self.programView.setItemDelegateForColumn(0, timeColumnDelegate)
        valueColumnDelegate = DoubleSpinBoxDelegate(parent=self.programView)
        self.programView.setItemDelegateForColumn(1, valueColumnDelegate)
        self.programSelectionModel = ItemSelectionModel(self.model,
                                                        self.programView)
        self.programView.setSelectionModel(self.programSelectionModel)

        self.__initActions()

        self.model.dataChanged.connect(lambda topLeft, bottomRight:
                                       self._showPreview())
        self.model.rowsInserted.connect(lambda parent, start, end:
                                        self._showPreview())

    def __initActions(self):

        def icon(name):
            return QtGui.QIcon.fromTheme(
                name, QtGui.QIcon(":/icons/Tango/%s.svg" % name))

        def viewPaste():
            try:
                self.programSelectionModel.paste()
            except IndexError:
                QtWidgets.QMessageBox.critical(
                    self.programView,  # parent
                    "Invalid clipboard data",  # title
                    "The number of columns in the clipboard is too large.")

        self.copyAction = QtWidgets.QAction(
            icon("edit-copy"), "Copy", self,
            shortcut=QtGui.QKeySequence.Copy,
            triggered=self.programSelectionModel.copy)
        self.pasteAction = QtWidgets.QAction(
            icon("edit-paste"), "Paste", self,
            shortcut=QtGui.QKeySequence.Paste,
            triggered=viewPaste)
        self.addRowAction = QtWidgets.QAction(
            icon("list-add"), "Add row", self,
            triggered=self.programSelectionModel.insertRow)
        self.removeRowAction = QtWidgets.QAction(
            icon("list-remove"), "Remove row", self,
            triggered=self.programSelectionModel.removeRows)
        self.startProgramAction = QtWidgets.QAction(
            icon("media-playback-start"), "Start program", self,
            triggered=self.startProgram)
        self.stopProgramAction = QtWidgets.QAction(
            icon("media-playback-stop"), "Stop program", self,
            triggered=self.stopProgram)
        self.startAllProgramsAction = QtWidgets.QAction(
            icon("media-seek-forward"), "Start all programs", self,
            triggered=self.startAllPrograms)
        self.stopAllProgramsAction = QtWidgets.QAction(
            icon("process-stop"), "Stop all programs", self,
            triggered=self.stopAllPrograms)

        self.toolBar.addActions((self.startProgramAction,
                                 self.stopProgramAction,
                                 self.startAllProgramsAction,
                                 self.stopAllProgramsAction,
                                 self.copyAction,
                                 self.pasteAction,
                                 self.addRowAction,
                                 self.removeRowAction))
        self.toolBar.insertSeparator(self.copyAction)
        self.toolBar.insertSeparator(self.addRowAction)

        self.programView.addAction(self.copyAction)
        self.programView.addAction(self.pasteAction)
        self.programView.addAction(self.addRowAction)
        self.programView.addAction(self.removeRowAction)

    def _clearPreview(self):
        while self._previewPlotItems:
            self._previewPlotItems.pop().remove()

    def _showPreview(self):
        self._clearPreview()
        for row in range(self.model.rowCount()):
            rootItem = self.model.item(row, 0)
            data = ProfileData.fromRootItem(rootItem).array
            if data.size > 1:
                label = (self.driverModel.verticalHeaderItem(row).text()
                         if self.driverModel else "%i" % row)
                line = Line(data[0], data[1], label=label)
                self.axes.add_artist(line)
                self._previewPlotItems.append(line)
        self.scaleToArtists(self._previewPlotItems)
        self.previewPlot.draw_idle()

    @property
    def _currentRow(self):
        """Set in `setProgramTableRoot`."""
        rootIndex = self.programView.rootIndex()
        return -1 if not rootIndex.isValid() else rootIndex.row()

    def setDriverModel(self, driverModel):
        self.driverModel = driverModel

    @Slot()
    def populate(self):
        """Called when the model has been populated.

        Generate the program tree.

        """
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["time /s", "setpoint"])
        for root in range(self.driverModel.rowCount()):
            rootItem = QtGui.QStandardItem(
                self.driverModel.verticalHeaderItem(root).text())
            rootItem.setEditable(False)
            self.model.invisibleRootItem().appendRow(rootItem)
            for row in range(8):
                rootItem.appendRow(
                    [QtGui.QStandardItem(), QtGui.QStandardItem()])

    def setProgramTableRoot(self, row):
        if None in (self.programColumn, self.driverModel):
            return
        self.programView.setRootIndex(self.model.index(row, 0))
        if not self.driverModel:
            return
        delegate = self.programView.itemDelegateForColumn(1)
        item = self.driverModel.item(0, self.programColumn)
        if item.minimum() is not None:
            delegate.setMinimum(item.minimum())
        if item.maximum() is not None:
            delegate.setMaximum(item.maximum())

    def startProgram(self, row=None):
        """Emit startRequested signal for `row`."""
        if row is None:
            row = self._currentRow
        self.startRequested.emit(row)

    def stopProgram(self, row=None):
        """Emit stopRequested signal for `row`."""
        if row is None:
            row = self._currentRow
        self.stopRequested.emit(row)

    def startAllPrograms(self):
        """Start or restart every program."""
        for row in range(self.model.rowCount()):
            self.startProgram(row)

    def stopAllPrograms(self):
        """Stop every program."""
        for row in range(self.model.rowCount()):
            self.stopProgram(row)


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    widget = ProgramWidget()
    widget.startRequested.connect(lambda row: print("start %i" % row))
    widget.stopRequested.connect(lambda row: print("stop %i" % row))
    root = QtGui.QStandardItem("root")
    root.setEditable(False)
    for row in range(8):
        root.appendRow([QtGui.QStandardItem(), QtGui.QStandardItem()])
    widget.model.invisibleRootItem().appendRow(root)
    widget.programView.setRootIndex(root.index())
    widget.show()
    sys.exit(app.exec_())
