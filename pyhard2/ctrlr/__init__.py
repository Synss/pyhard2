# This file is part of pyhard2 - An object-oriented framework for the
# development of instrument drivers.

# Copyright (C) 2012-2014 Mathias Laurin, GPLv3


"""Qt4 graphical user interface for the controllers.

"""
import logging
from collections import defaultdict
import StringIO as _StringIO
import csv as _csv
import zipfile as _zipfile
from functools import partial as _partial
import time as _time

import argparse
import yaml
from importlib import import_module  # DashboardConfig

import sip as _sip
for _type in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    _sip.setapi(_type, 2)

from PyQt4 import QtCore, QtGui, QtSvg, uic
Qt = QtCore.Qt
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal
import PyQt4.Qwt5 as Qwt

import pyhard2
from pyhard2 import pid
import pyhard2.driver as drv
import pyhard2.rsc


logging.basicConfig()
logger = logging.getLogger("pyhard2")


def Config(section, description="pyhard2 GUI configuration"):
    """Handle command line arguments and configuration files to
    initialize `Controllers`.

    Command line arguments:
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
    parser.add_argument('-p', '--port')
    parser.add_argument('-n', '--nodes', nargs="*", default=[])
    parser.add_argument('-m', '--names', nargs="*", default=[])
    parser.add_argument('-v', '--virtual', action="store_true")
    parser.add_argument('file', type=argparse.FileType("r"), nargs="?")
    parser.add_argument('config', nargs="*")
    args = parser.parse_args()
    if args.file:
        config = yaml.load(args.file).get(section)
        args.port = config.iterkeys().next()
        for __ in config.itervalues():
            for index, node_config in enumerate(__):
                args.nodes.append(node_config.get("node", index))
                args.names.append(node_config.get("name", u"%s" % index))
    if not args.port:
        args.virtual = True
    return args


class DashboardConfig(object):

    """Extend the config file format described in :func:`Config` to
    launch the `Dashboard` interface.

    The config files are extended with a `dashboard` section such as

    .. code-block:: yaml

        dashboard:
            name: Dashboard
            image: :/img/gaslines.svg
            labels:
                - name: LABEL1
                  pos: [0.25, 0.25]
                - name: LABEL2
                  pos: [0.5, 0.25]
                - name: LABEL3
                  pos: [0.75, 0.25]

    Where `Dashboard` is the name of the window. ``image:`` points to an
    svg file that will be displayed in the background of the window.
    ``labels:`` is a list of text labels containing the text `LABEL1`,
    `LABEL2`, and `LABEL3` displayed at the position given by ``pos:``
    as `(x,y)` pairs of relative coordinates.  `x` and `y` can be any
    value between 0 and 1.

    The other nodes also require the `pos` data in the format specified
    above, and optional ``scale`` and ``angle`` data may be passed as
    well.  Such as the previous file may become

    .. code-block:: yaml

        MODULE:
            COM1:
                - node: 1
                  name: first
                  pos: [0.25, 0.5]

                - node: 2
                  name: second
                  pos: [0.5, 0.5]
                  scale: 0.5
                  angle: 180

                - node: 3
                  name: third
                  pos: [0.75, 0.5]

    - `pos` gives the position as ``[x, y]`` pairs of relative
      coordinates (`x` and `y` are values between 0 and 1)  for the
      widget of the corresponding node.
    - `scale` scales the widget by the given amount.
    - `angle` rotates the widget by the given amount, in degree.

    Example:
        From the root directory of a working installation of `pyhard2`,
        the following line starts a dashboard containing virtual
        instruments::

            python pyhard2.ctrlr.__init__.py circat.yml -v

    """
    def __init__(self, filename):
        with open(filename, "rb") as file:
            self.yaml = yaml.load(file)
        self.windowTitle = "Dashboard"
        self.backgroundItem = QtGui.QGraphicsRectItem(0, 0, 640, 480)
        self.controllers = {}
        self.labels = {}

    def setupUi(self, dashboard):
        dashboard.setWindowTitle(self.windowTitle)
        dashboard.setBackgroundItem(self.backgroundItem)
        for text, (x, y) in self.labels.iteritems():
            textItem = dashboard.addSimpleText(text)
            textItem.setFlags(textItem.flags()
                              | QtGui.QGraphicsItem.ItemIgnoresTransformations)
            textItem.setPos(dashboard.mapToScene(QtCore.QPointF(x, y)))
        for controller, proxyWidgets in self.controllers.iteritems():
            dashboard.addControllerAndWidgets(controller, proxyWidgets)

    def parse(self):
        section = self.yaml.pop("dashboard")
        try:
            self.backgroundItem = QtSvg.QGraphicsSvgItem(section.pop("image"))
        except KeyError:
            pass
        self.windowTitle = section.pop("name", self.windowTitle)
        for name, pos in (dct.itervalues()
                          for dct in section.pop("labels", [])):
            self.labels[name] = pos

        for module, section in self.yaml.iteritems():
            controller = import_module("pyhard2.ctrlr.%s" % module)\
                    .createController()
            self.controllers[controller] = []  # empty proxyWidget list
            for subsection in section.itervalues():
                for row, config in enumerate(subsection):
                    try:
                        x, y = config["pos"]
                    except KeyError:
                        continue
                    column = 0
                    proxyWidget = QtGui.QGraphicsProxyWidget()
                    proxyWidget.setWidget(controller.editorPrototype[column]
                                    .__class__())  # XXX
                    proxyWidget.setToolTip(config.get("name", row))
                    proxyWidget.setPos(x, y)
                    proxyWidget.rotate(config.get("angle", 0))
                    proxyWidget.setScale(config.get("scale", 1.5))
                    if isinstance(proxyWidget.widget(), QtGui.QAbstractSpinBox):
                        proxyWidget.setFlags(proxyWidget.flags()
                                             | proxyWidget.ItemIgnoresTransformations)
                    self.controllers[controller].append(proxyWidget)


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


class ListData(Qwt.QwtData):
    
    """Custom `QwtData` mapping a list onto `x,y` values."""
    X, Y = range(2)

    def __init__(self):
        super(ListData, self).__init__()
        self._historySize = 500
        self._history = []
        self._data = []

    def __iter__(self):
        """Iterate on the data."""
        return iter(self._history + self._data)

    def historySize(self):
        """How many points of history to display after exportAndTrim."""
        return self._historySize

    def setHistorySize(self, historySize):
        """Set how many points of history to display after exportAndTrim."""
        self._historySize = historySize

    def copy(self):
        """Return self."""
        return self

    def size(self):
        """Return length of data."""
        return len(self._history) + len(self._data)

    def sample(self, i):
        """Return `x,y` values at `i`."""
        try:
            return self._history[i]
        except IndexError:
            return self._data[i - len(self._history)]

    def x(self, i):
        """Return `x` value."""
        return self.sample(i)[ListData.X]

    def y(self, i):
        """Return `y` value."""
        return self.sample(i)[ListData.Y]

    def append(self, xy):
        """Add `x,y` values to the data.

        Does nothing if None is in `xy`.
        """
        if None in xy: return
        self._data.append(xy)

    def clear(self):
        """Clear the data in place."""
        self._history = []
        self._data = []

    def exportAndTrim(self, csvfile):
        """Export the data to `csvfile` and trim it.

        The data acquired since the previous call is saved to `csvfile`
        and `historySize` points are kept.  The rest of the data is
        deleted.
        """
        currentData, self._data = self._data, []
        self._history.extend(currentData)
        self._history = self._history[-self._historySize:]
        _csv.writer(csvfile, delimiter="\t").writerows(currentData)


class TimeSeriesData(ListData):

    """A `ListData` to plot values against time.

    Note:
        The time is set to zero upon instantiation.

    """
    def __init__(self):
        super(TimeSeriesData, self).__init__()
        self.__start = _time.time()

    def append(self, value):
        """Append `time, value` to the list."""
        super(TimeSeriesData, self).append(
            (_time.time() - self.__start, value))


class ProfileData(Qwt.QwtData):

    """Custom `QwtData` handling a QStandardItemModel with two columns
    as `x, y` values.

    Parameters:
        rootItem (QStandardItem): The root item of the model.

    """
    X, Y = range(2)

    def __init__(self, rootItem):
        super(ProfileData, self).__init__()
        self._rootItem = rootItem
        self._model = self._rootItem.model()

    def __iter__(self):
        """Iterate on the model."""
        return (self.sample(i) for i in range(self.size()))

    def copy(self):
        """Return self."""
        return self

    def size(self):
        """Return the number of rows under `rootItem`.

        Note:
            Rows where values cannot be converted to `float` are not
            counted.

        """
        size = 0
        for row in range(self._model.rowCount(self._rootItem.index())):
            x = self._rootItem.child(row, ProfileData.X)
            y = self._rootItem.child(row, ProfileData.Y)
            try:
                # check validity
                x, y = float(x.text()), float(y.text())
            except ValueError:
                pass
            else:
                size += 1
        return size

    def sample(self, i):
        """Return `x,y` values at `i`.

        Raises:
            IndexError: if `i` is larger than the model.

        """
        if i < 0:
            i += self.size()
        if i >= self.size():
            raise IndexError("%s index out of range" % self.__class__.__name__)
        return (float(self._rootItem.child(i, ProfileData.X).text()),
                float(self._rootItem.child(i, ProfileData.Y).text()))

    def x(self, i):
        """Return `x` value at `i`."""
        return self.sample(i)[ProfileData.X]

    def y(self, i):
        """Return `y` value at `i`."""
        return self.sample(i)[ProfileData.Y]


class PlotZoomer(Qwt.QwtPlotZoomer):

    """QwtPlotZoomer for zooming on QwtPlot."""

    def __init__(self, canvas):
        super(PlotZoomer, self).__init__(Qwt.QwtPlot.xBottom,
                                         Qwt.QwtPlot.yLeft,
                                         Qwt.QwtPicker.DragSelection,
                                         Qwt.QwtPicker.AlwaysOff,
                                         canvas)
        self.setRubberBandPen(QtGui.QPen(QtGui.QColor("white")))
        # ZOOM IN: left and drag; ZOOM OUT: shift + left
        self.setMousePattern(Qwt.QwtEventPattern.MouseSelect2,
                             Qt.LeftButton, Qt.ShiftModifier)
        self.setTrackerPen(QtGui.QPen(QtGui.QColor("white")))
        self.zoomed.connect(self._zoomed)

    def _zoomed(self, rect):
        if self.zoomRectIndex() == 0:
            self.clearZoomStack()

    def clearZoomStack(self):
        """Force autoscaling and clear the zoom stack."""
        self.plot().setAxisAutoScale(Qwt.QwtPlot.yLeft)
        self.plot().setAxisAutoScale(Qwt.QwtPlot.yRight)
        self.plot().setAxisAutoScale(Qwt.QwtPlot.xBottom)
        self.plot().setAxisAutoScale(Qwt.QwtPlot.xTop)
        self.plot().replot()
        self.setZoomBase()


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
        self.finished.connect(self._timer.stop)
        self.started.connect(self._shoot)
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
        if self._running: self.stop()  # restart
        self._running = True
        self.started.emit()

    @Slot()
    def stop(self):
        """Stop the program."""
        if not self._running: return  # ignore
        self._running = False
        self.finished.emit()
        self._index = -1

    @Slot()
    def _shoot(self):
        """Emit a new value if it exists or terminate the program."""
        self._index += 1
        self.value.emit(self._profile.y(self._index))
        try:
            # relative time
            dt = self._dt
        except IndexError:
            # we give a chance to derived classes to do something before
            # finishing
            QtCore.QTimer.singleShot(100, self.stop)
        else:
            self._timer.start(1000 *  dt)  # msec


class SetpointRampProgram(SingleShotProgram):

    """Program that performs setpoint ramps."""

    def __init__(self):
        super(SetpointRampProgram, self).__init__()
        self._ramp = None
        self._timer.setSingleShot(False)
        self.started.connect(self._timer.start)

    def setProfile(self, profile):
        """Set the profile to `profile`."""
        super(SetpointRampProgram, self).setProfile(profile)
        self._ramp = pid.Profile(list(self._profile)).ramp()

    @Slot()
    def _shoot(self):
        """Emit a new value if it exists or terminate the program."""
        try:
            self.value.emit(self._ramp.next())
        except StopIteration:
            self.value.emit(self._profile.y(-1))
            self.stop()


class DoubleClickEventFilter(QtCore.QObject):

    """Emit doubleClicked signal on MouseButtonDblClick event."""

    doubleClicked = Signal()

    def __init__(self, parent):
        super(DoubleClickEventFilter, self).__init__(parent)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonDblClick:
            self.doubleClicked.emit()
            return True
        return False


class FormatTextDelegate(QtGui.QStyledItemDelegate):

    """QStyledItemDelegate formatting the text displayed."""

    def __init__(self, format="%.2f", parent=None):
        super(FormatTextDelegate, self).__init__(parent)
        self._format = format

    def displayText(self, value, locale):
        return self._format % value


class DoubleSpinBoxDelegate(QtGui.QStyledItemDelegate):

    """Item delegate for editing models with a spin box.

    Every property of the spin box can be set on the delegate with the
    methods from QDoubleSpinBox.

    Args:
        spinBox: A spin box prototype to use for editing, defaults to
            `QDoubleSpinBox` if not given.

    Methods:
        decimals()
        setDecimals(prec)
            This property holds the precision of the spin box, in
            decimals.
        minimum()
        setMinimum(min)
            This property holds the minimum value of the spin box.
        maximum()
        setMaximum(max)
            This property holds the maximum value of the spin box.
        setRange(minimum, maximum)
            Convenience function to set the `minimum` and `maximum`
            values with a single function call.
        singleStep()
        setSingleStep(val)
            This property holds the step value.
        prefix()
        setPrefix(prefix)
            This property holds the spin box's prefix.
        suffix()
        setSuffix(suffix)
            This property holds the spin box's suffix.

    """
    def __init__(self, spinBox=None, parent=None):
        super(DoubleSpinBoxDelegate, self).__init__(parent)
        self._spinBox = QtGui.QDoubleSpinBox() if spinBox is None else spinBox

    def __repr__(self):
        return "%s(spinBox=%r, parent=%r)" % (
            self.__class__.__name__, self._spinBox, self.parent())

    def __getattr__(self, name):
        """Set properties on the spin box."""
        try:
            return object.__getattribute__(self._spinBox, name)
        except AttributeError:
            # Fail with the correct exception.
            return self.__getattribute__(name)

    def createEditor(self, parent, option, index):
        """Return a QDoubleSpinBox."""
        if index.isValid():
            spinBox = self._spinBox.__class__(parent)
            # copy properties
            spinBox.setDecimals(self._spinBox.decimals())
            spinBox.setMaximum(self._spinBox.maximum())
            spinBox.setMinimum(self._spinBox.minimum())
            spinBox.setPrefix(self._spinBox.prefix())
            spinBox.setSingleStep(self._spinBox.singleStep())
            spinBox.setSuffix(self._spinBox.suffix())
            spinBox.editingFinished.connect(self._commitAndCloseEditor)
            return spinBox
        else:
            return super(DoubleSpinBoxDelegate, self).createEditor(
                parent, option, index)

    def setEditorData(self, spinBox, index):
        """Set spin box value to `index.data()`."""
        if index.isValid():
            try:
                spinBox.setValue(index.data())
            except TypeError:
                pass

    def setModelData(self, spinBox, model, index):
        """Set model data to `spinBox.value()`."""
        if index.isValid():
            model.setData(index, spinBox.value())
        else:
            super(DoubleSpinBoxDelegate, self).setModelData(
                spinBox, model, index)

    def _commitAndCloseEditor(self):
        """Commit data and close editor."""
        self.commitData.emit(self.sender())
        self.closeEditor.emit(self.sender(), self.NoHint)


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


class ButtonDelegate(QtGui.QStyledItemDelegate):

    """Item delegate for editing models with a button.

    Args:
        button: The button prototype to use for editing, defaults to
            `QPushButton` if not given.

    """
    def __init__(self, button=None, parent=None):
        super(ButtonDelegate, self).__init__(parent)
        self._btn = QtGui.QPushButton() if button is None else button
        self._btn.setParent(parent)
        self._btn.hide()

    def __repr__(self):
        return "%s(button=%r, parent=%r)" % (
            self.__class__.__name__, self._btn, self.parent())

    def sizeHint(self, option, index):
        return super(ButtonDelegate, self).sizeHint(option, index)

    def createEditor(self, parent, option, index):
        return None

    def setModelData(self, editor, model, index):
        model.setData(index, editor.isChecked())

    def setEditorData(self, editor, index):
        editor.setChecked(index.data() if index.data() else Qt.Unchecked)

    def paint(self, painter, option, index):
        self._btn.setChecked(index.data() if index.data() else Qt.Unchecked)
        self._btn.setGeometry(option.rect)
        if option.state & QtGui.QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        pixmap = QtGui.QPixmap.grabWidget(self._btn)
        painter.drawPixmap(option.rect.x(), option.rect.y(), pixmap)

    def editorEvent(self, event, model, option, index):
        """Change the state of the editor and the data in the model when
        the user presses the left mouse button, Key_Space or Key_Select
        iff the cell is editable.

        """
        if (int(index.flags()) & Qt.ItemIsEditable and
            (event.type() in (QtCore.QEvent.MouseButtonRelease,
                              QtCore.QEvent.MouseButtonDblClick) and
             event.button() == Qt.LeftButton) or
            (event.type() == QtCore.QEvent.KeyPress and
             event.key() in (Qt.Key_Space, Qt.Key_Select))):
                self._btn.toggle()
                self.setModelData(self._btn, model, index)
                self.commitData.emit(self._btn)
                return True
        return False


class ItemSelectionModel(QtGui.QItemSelectionModel):

    """QItemSelectionModel with copy/paste and a part of the
    QTableWidget interface.

    """
    def __init__(self, model, parent=None):
        super(ItemSelectionModel, self).__init__(model, parent)

    def currentRow(self):
        """Return the row of the current item."""
        return self.currentIndex().row()

    def currentColumn(self):
        """Return the column of the current item."""
        return self.currentIndex().column()

    def _parentItem(self):
        """Return the parent of the current item."""
        return self.model().itemFromIndex(self.currentIndex()).parent()

    def insertRow(self):
        """Insert an empty row into the table at the current row."""
        parent = self._parentItem()
        parent.insertRow(self.currentRow(),
               [QtGui.QStandardItem() for __ in range(parent.columnCount())])

    def insertColumn(self):
        """Insert an empty column into the table at the current column."""
        parent = self._parentItem()
        parent.insertColumn(self.currentColumn(),
               [QtGui.QStandardItem() for __ in range(parent.rowCount())])

    def removeRows(self):
        """Remove the selected rows."""
        currentIndex = self.currentIndex()
        selection = self.selectedRows()
        if not selection: selection = [currentIndex]
        parent = self._parentItem()
        rowCount = parent.rowCount()
        for row in (index.row() for index in selection):
            parent.removeRow(row)
        parent.setRowCount(rowCount)

    def removeColumns(self):
        """Remove the selected columns."""
        currentIndex = self.currentIndex()
        selection = self.selectedColumns()
        if not selection: selection = [currentIndex]
        parent = self._parentItem()
        columnCount = parent.columnCount()
        for column in (index.column() for index in selection):
            parent.removeColumn(column)
        parent.setColumnCount(columnCount)

    def copy(self):
        """Copy the values in the selection to the clipboard."""
        previous = QtCore.QModelIndex()
        fields = []
        for index in sorted(self.selectedIndexes()):
            if index.row() is previous.row():
                fields[-1].append(index.data())
            else:
                fields.append([index.data()])
            previous = index
        csvfile = _StringIO.StringIO()
        writer = _csv.writer(csvfile)
        writer.writerows(fields)
        QtGui.QApplication.clipboard().setText(csvfile.getvalue())

    def paste(self):
        """Paste values in the clipboard at the current item.

        Raises:
            IndexError: if the data in the clipboard does not fit in the
                model.

        """
        currentIndex = self.currentIndex()
        parent = self._parentItem()
        csvfile = _StringIO.StringIO(QtGui.QApplication.clipboard().text())
        try:
            dialect = _csv.Sniffer().sniff(csvfile.read(1024))
        except _csv.Error:
            return
        csvfile.seek(0)
        reader = _csv.reader(csvfile, dialect)
        for i, line in enumerate(reader):
            if currentIndex.column() + len(line) > parent.columnCount():
                raise IndexError
            for j, text in enumerate(line):
                parent.setChild(currentIndex.row() + i,
                                currentIndex.column() + j,
                                QtGui.QStandardItem(text))


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
            logger.error("%s:%s:%s" % (
                self.command().reader,
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
        return (self.item(row, column) for row in range(self.rowCount())
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

        self.dataPlotZoomer = PlotZoomer(self.dataPlot.canvas())

        self.programPanel.setSizePolicy(QtGui.QSizePolicy.Fixed,
                                        QtGui.QSizePolicy.Expanding)

        self.programView.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.Stretch)
        self.programView.horizontalHeader().setResizeMode(
            0, QtGui.QHeaderView.ResizeToContents)

        self.programTableToolBar = QtGui.QToolBar(self.programPanel)
        self.programPanel.layout().insertWidget(0, self.programTableToolBar)

        self.dataPlotLogScaleCB.stateChanged.connect(self.setDataPlotLogScale)

    def setDataPlotLogScale(self, state):
        """Change the scale of `dataPlot` to log or linear."""
        if state:
            scale = Qwt.QwtLog10ScaleEngine()
            scale.setAttribute(Qwt.QwtScaleEngine.Symmetric)
        else:
            scale = Qwt.QwtLinearScaleEngine()
        self.dataPlot.setAxisScaleEngine(0, scale)

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

    def __init__(self, driver, windowTitle="", uifile="", parent=None):
        super(Controller, self).__init__(parent)
        self.ui = ControllerUi(uifile)
        # UI methods
        self.windowTitle = self.ui.windowTitle
        self.setWindowTitle = self.ui.setWindowTitle
        self.show = self.ui.show
        self.close = self.ui.close
        self.setColumnHidden = self.ui.driverView.setColumnHidden
        self.isColumnHidden = self.ui.driverView.isColumnHidden

        self.setWindowTitle(windowTitle)
        self.editorPrototype = defaultdict(QtGui.QDoubleSpinBox)

        self._specialColumnMapper = dict(
            programmable=self.setProgrammableColumn,
            pidp=self.setPidPColumn,
            pidi=self.setPidIColumn,
            pidd=self.setPidDColumn,)

        self.programPool = defaultdict(SingleShotProgram)
        self._programmableColumn = None

        self._previewPlotCurves = {}
        self._previewPlotMarkers = {}
        self._dataPlotCurves = {}
        self._dataLog = defaultdict(TimeSeriesData)

        self._driverModel = DriverModel(driver, self)
        self.populated.connect(self._setupWithConfig)
        self.ui.driverView.setModel(self._driverModel)

        self.ui.driverView.selectionModel().currentRowChanged.connect(
            self._selectionModel_currentRowChanged)
        self.ui.dataPlotSingleInstrumentCB.stateChanged.connect(
            self._dataPlotSingleInstrumentCB_stateChanged)

        self._programModel = QtGui.QStandardItemModel(self)
        self._programModel.setHorizontalHeaderLabels([u"time /s", u"setpoint"])
        self.ui.programView.setModel(self._programModel)
        timeColumnDelegate = DoubleSpinBoxDelegate(parent=self.ui.programView)
        timeColumnDelegate.setRange(0.0, 604800.0)  # 7 days
        self.ui.programView.setItemDelegateForColumn(0, timeColumnDelegate)
        valueColumnDelegate = DoubleSpinBoxDelegate(parent=self.ui.programView)
        self.ui.programView.setItemDelegateForColumn(1, valueColumnDelegate)
        self.programSelectionModel = ItemSelectionModel(self._programModel,
                                                        self.ui.programView)
        self.ui.programView.setSelectionModel(self.programSelectionModel)

        self.ui.driverView.selectionModel().currentRowChanged.connect(
            self.updateProgramTable)
        self.ui.driverView.selectionModel().currentRowChanged.connect(
            self.updateStartStopProgramButton)

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

        self.__initProgramTableActions()

        self.pidBoxMapper = QtGui.QDataWidgetMapper(self.ui.pidBox)
        self.pidBoxMapper.setModel(self._driverModel)
        self.pidBoxMapper.setSubmitPolicy(QtGui.QDataWidgetMapper.AutoSubmit)
        self.pidBoxMapper.setItemDelegate(
            ItemRangedSpinBoxDelegate(parent=self.pidBoxMapper))
        self.ui.driverView.selectionModel().currentRowChanged.connect(
            self.pidBoxMapper.setCurrentModelIndex)
        self.populated.connect(self.pidBoxMapper.toFirst)

        self.ui.driverView.customContextMenuRequested.connect(
            self.on_instrumentsTable_customContextMenuRequested)
        self.ui.dataPlot.customContextMenuRequested.connect(
            self.on_dataPlot_customContextMenuRequested)
        self.ui.programView.customContextMenuRequested.connect(
            self.on_programTable_customContextMenuRequested)

    def __initProgramTableActions(self):
        def startStopProgram(checked):
            row = self.ui.driverView.currentIndex().row()
            running = self.programPool[row].isRunning()
            if (checked and running) or (not checked and not running):
                return
            elif checked and not running:
                self.startProgram(row)
            elif not checked and running:
                self.programPool[row].stop()

        def icon(name):
            return QtGui.QIcon.fromTheme(
                name, QtGui.QIcon(":/icons/Tango/%s.svg" % name))

        def viewPaste():
            try:
                self.programSelectionModel.paste()
            except IndexError:
                QtGui.QMessageBox.critical(
                    self.ui.programView,  # parent
                    "Invalid clipboard data",  # title
                    "The number of columns in the clipboard is too large.")

        self.copyAction = QtGui.QAction(
            icon("edit-copy"), u"Copy", self, shortcut=QtGui.QKeySequence.Copy,
            triggered=self.programSelectionModel.copy)

        self.pasteAction = QtGui.QAction(
            icon("edit-paste"), u"Paste", self,
            shortcut=QtGui.QKeySequence.Paste,
            triggered=viewPaste)

        self.addRowAction = QtGui.QAction(
            icon("list-add"), u"Add row", self,
            triggered=self.programSelectionModel.insertRow)

        self.removeRowAction = QtGui.QAction(
            icon("list-remove"), u"Remove row", self,
            triggered=self.programSelectionModel.removeRows)

        self.startStopProgramAction = QtGui.QAction(
            icon("media-playback-start"), u"Start program", self,
            checkable=True, triggered=startStopProgram)

        self.startAllProgramsAction = QtGui.QAction(
            icon("media-seek-forward"), u"Start all programs", self,
            triggered=self.startAllPrograms)

        self.stopAllProgramsAction = QtGui.QAction(
            icon("process-stop"), u"Stop all programs", self,
            triggered=self.stopAllPrograms)

        self.ui.programTableToolBar.addActions((self.startStopProgramAction,
                                                self.startAllProgramsAction,
                                                self.stopAllProgramsAction,
                                                self.copyAction,
                                                self.pasteAction,
                                                self.addRowAction,
                                                self.removeRowAction))
        self.ui.programTableToolBar.insertSeparator(self.copyAction)
        self.ui.programTableToolBar.insertSeparator(self.addRowAction)

    def on_instrumentsTable_customContextMenuRequested(self, pos):
        column = self.ui.driverView.columnAt(pos.x())
        row = self.ui.driverView.rowAt(pos.y())
        item = self._driverModel.item(row, column)
        rightClickMenu = QtGui.QMenu(self.ui.driverView)
        rightClickMenu.addActions(
            [QtGui.QAction("Polling", self, checkable=True,
                           checked=item.isPolling(), triggered=item.setPolling),
             QtGui.QAction("Logging", self, checkable=True,
                           checked=item.isLogging(), triggered=item.setLogging)
            ])
        rightClickMenu.exec_(self.ui.driverView.viewport()
                             .mapToGlobal(pos))

    def on_dataPlot_customContextMenuRequested(self, pos):
        def clear():
            """Clear the `dataPlot`."""
            for plotItem in self.ui.dataPlot.itemList():
                plotItem.data().clear()

        def exportAsCsv(dataPlot):
            """Export the content of a `dataPlot` to csv files."""
            try:
                zipfilename = QtGui.QFileDialog.getSaveFileName(
                    dataPlot, "Export zipped in file",
                    filter="Zip files (*.zip)",
                    options=QtGui.QFileDialog.DontConfirmOverwrite)  # append
                if not zipfilename.endswith(".zip"):
                    zipfilename += ".zip"
                with _zipfile.ZipFile(zipfilename, "a") as zipfile:
                    for curve in dataPlot.itemList():
                        csvfile = _StringIO.StringIO()
                        curve.data().exportAndTrim(csvfile)
                        filename = " ".join((curve.title().text(),
                                             _time.strftime("%Y%m%dT%H%M%S")))
                        zipfile.writestr(filename, csvfile.getvalue())
            except IOError:
                pass  # User canceled QFileDialog

        rightClickMenu = QtGui.QMenu(self.ui.dataPlot)
        rightClickMenu.addActions([
            QtGui.QAction("Zoom out", self.ui.dataPlot,
                          triggered=self.ui.dataPlotZoomer.clearZoomStack),
            QtGui.QAction("Export as csv", self.ui.dataPlot,
                          triggered=_partial(exportAsCsv, self.ui.dataPlot)),
            QtGui.QAction("Clear", self.ui.dataPlot, triggered=clear)])
        pos = self.ui.dataPlot.mapToGlobal(pos)
        rightClickMenu.exec_(pos)

    def on_programTable_customContextMenuRequested(self, pos):
        rightClickMenu = QtGui.QMenu(self.ui.programView)
        rightClickMenu.addAction(self.copyAction)
        rightClickMenu.addAction(self.pasteAction)
        rightClickMenu.addAction(self.addRowAction)
        rightClickMenu.addAction(self.removeRowAction)
        pos = self.ui.programView.viewport().mapToGlobal(pos)
        rightClickMenu.exec_(pos)

    def _selectionModel_currentRowChanged(self, current, previous):
        if self.ui.dataPlotSingleInstrumentCB.isChecked():
            self._setDataPlotCurveVisibilityForRow(previous.row(), False)
            self._setDataPlotCurveVisibilityForRow(current.row(), True)

        self._setDataPlotCurveZ(previous.row(), 20)
        self._setDataPlotCurvePenForRow(previous.row(), QtGui.QPen(Qt.black))
        self._setDataPlotCurveZ(current.row(), 21)
        self._setDataPlotCurvePenForRow(current.row(), QtGui.QPen(Qt.red))
        self.ui.dataPlot.replot()

    def _dataPlotSingleInstrumentCB_stateChanged(self, state):
        selectionModel = self.ui.driverView.selectionModel()
        selection = selectionModel.selectedRows()
        if not selection: return
        row = selection.pop().row()
        for row_, curve in self._dataPlotCurves.iteritems():
            self._setDataPlotCurveVisibilityForRow(row_, not state or
                                                            row_ is row)
        self._setDataPlotCurvePenForRow(row, QtGui.QPen(Qt.black) if state else
                                             QtGui.QPen(Qt.red))
        self.ui.dataPlot.replot()

    def _setDataPlotCurveZ(self, row, z):
        if row is -1: return  # ignore invalid index
        for curve in self._dataPlotCurves[row]:
            curve.setZ(z)

    def _setDataPlotCurveVisibilityForRow(self, row, visible=True):
        if row is -1: return  # ignore invalid index
        for curve in self._dataPlotCurves[row]:
            curve.setVisible(visible)

    def _setDataPlotCurvePenForRow(self, row, pen):
        if row is -1: return  # ignore invalid index
        for curve in self._dataPlotCurves[row]:
            curve.setPen(pen)

    def _setupWithConfig(self):
        self._setupDataPlotCurves()
        self._setupPrograms()
        self._setupProgramTable()
        self._setupPreviewPlotCurves()

    def _setupProgramTable(self):
        for root in range(self._driverModel.rowCount()):
            rootItem = QtGui.QStandardItem(
                self._driverModel.verticalHeaderItem(root).text())
            rootItem.setEditable(False)
            self._programModel.invisibleRootItem().appendRow(rootItem)
            for row in range(8):
                rootItem.appendRow(
                    [QtGui.QStandardItem(), QtGui.QStandardItem()])

    def updateProgramTable(self, index):
        if self._programmableColumn is None: return
        self.ui.programView.setRootIndex(
            self._programModel.index(index.row(), 0))
        item = self._driverModel.item(0, self._programmableColumn)
        delegate = self.ui.programView.itemDelegateForColumn(1)
        if item.minimum() is not None:
            delegate.setMinimum(item.minimum())
        if item.maximum() is not None:
            delegate.setMaximum(item.maximum())

    def updateStartStopProgramButton(self, index):
        running = self.programPool[index.row()].isRunning()
        self.startStopProgramAction.setChecked(running)
        self.startStopProgramAction.setIcon(QtGui.QIcon.fromTheme(
            "media-playback-%s" % ("stop" if running else "start"),
            QtGui.QIcon(":/icons/Tango/media-playback-%s.svg"
                        % ("stop" if running else "start"))))

    def _setupDataPlotCurves(self):
        """Initialize GUI elements with the model. """
        for item in self._driverModel:
            text = "%s %s" % (
                self._driverModel.verticalHeaderItem(item.row()).text(),
                self._driverModel.horizontalHeaderItem(item.column()).text())
            dataPlotCurve = Qwt.QwtPlotCurve(text)
            dataPlotCurve.setData(self._dataLog[item])
            dataPlotCurve.attach(self.ui.dataPlot)
            self._dataPlotCurves.setdefault(item.row(), [])\
                    .append(dataPlotCurve)

    def updatePreviewPlotCurve(self, row):
        if row is -1: return  # Comes from invalid index
        previewPlotCurve = self._previewPlotCurves[row]
        previewPlotMarker = self._previewPlotMarkers[row]
        data = previewPlotCurve.data()
        previewPlotCurve.setVisible(data.size() > 1)
        previewPlotMarker.setVisible(data.size() > 1)
        if data.size() > 1:
            x, y = (0.5 * (sample(data.size() - 2) + sample(data.size() - 1))
                    for sample in (data.x, data.y))
            previewPlotMarker.setValue(x, y)
        self.ui.previewPlot.replot()

    def _setupPreviewPlotCurves(self):
        """Initialize GUI elements with the model."""
        if self._programmableColumn is None: return
        for row in range(self._driverModel.rowCount()):
            label = self._driverModel.verticalHeaderItem(row).text()
            previewPlotCurve = Qwt.QwtPlotCurve(label)
            previewPlotCurve.setData(
                ProfileData(self._programModel.item(row, 0)))
            previewPlotCurve.hide()
            previewPlotCurve.attach(self.ui.previewPlot)
            self._previewPlotCurves[row] = previewPlotCurve

            previewPlotMarker = Qwt.QwtPlotMarker()
            previewPlotMarker.setLabel(previewPlotCurve.title())
            previewPlotMarker.hide()
            previewPlotMarker.attach(self.ui.previewPlot)
            self._previewPlotMarkers[row] = previewPlotMarker

        self._programModel.dataChanged.connect(
            lambda topLeft, bottomRight:
            self.updatePreviewPlotCurve(topLeft.parent().row()))
        self._programModel.rowsInserted.connect(
            lambda parent, start, end:
            self.updatePreviewPlotCurve(parent.row()))

    def _setupPrograms(self):
        """Initialize programs with the model."""
        if self._programmableColumn is None: return

        def program_setInterval(program, dt):  # early binding necessary
            program.setInterval(1000 * dt)

        def updateStartStopProgramButton(row):
            self.updateStartStopProgramButton(
                self._driverModel.index(row, 0))

        for row in range(self._driverModel.rowCount()):
            program = self.programPool[row]
            item = self._driverModel.item(row, self._programmableColumn)
            program.value.connect(_partial(item.setData))
            program.started.connect(_partial(updateStartStopProgramButton, row))
            program.finished.connect(_partial(updateStartStopProgramButton, row))
            program.setInterval(1000 * self.ui.refreshRateEditor.value())
            self.ui.refreshRateEditor.valueChanged.connect(
                _partial(program_setInterval, program))
            self.programPool[row] = program

    @Slot()
    def replot(self):
        self.ui.dataPlot.replot()

    @Slot()
    def refreshData(self, force=False):
        for item in self._driverModel:
            if item.isPolling() or force:
                item.queryData()

    @Slot()
    def logData(self):
        for item in self._driverModel:
            if item.isLogging():
                self._dataLog[item].append(item.data())

    def startProgram(self, row):
        """Start the program at `row`."""
        if self._programmableColumn is None: return
        program = self.programPool[row]
        program.setProfile(ProfileData(self._programModel.item(row, 0)))
        program.start()

    def startAllPrograms(self):
        """Start or restart every program."""
        for row in range(self._programModel.rowCount()):
            self.startProgram(row)

    def stopAllPrograms(self):
        """Stop every program."""
        for program in self.programPool.itervalues():
            program.stop()

    @classmethod  # alt. ctor
    def virtualInstrumentController(cls, driver, windowTitle=""):
        """Initialize controller for the virtual instrument driver."""
        self = cls(driver)
        self.setWindowTitle(windowTitle)
        self.setWindowTitle(self.windowTitle() + u" [virtual]")
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
        return self._programmableColumn

    def setProgrammableColumn(self, column):
        """Set the programmable column to `column`."""
        self._programmableColumn = column

    def setPidPColumn(self, column):
        """Set the pid P column to `column`."""
        self.pidBoxMapper.addMapping(self.ui.pEditor, column)

    def setPidIColumn(self, column):
        """Set the pid I column to `column`."""
        self.pidBoxMapper.addMapping(self.ui.iEditor, column)

    def setPidDColumn(self, column):
        """Set the pid D column to `column`."""
        self.pidBoxMapper.addMapping(self.ui.dEditor, column)

    def populate(self):
        """Populate the driver table."""
        self._driverModel.populate()
        self.populated.emit()

    def closeEvent(self, event):
        self.timer.stop()
        super(Controller, self).closeEvent(event)


class DashboardUi(QtGui.QMainWindow):

    """QMainWindow for the dashboard.

    This class loads `uifile` if one is provided or default to the
    `ui/dashboard.ui` designer file.

    """
    def __init__(self, uifile=""):
        super(DashboardUi, self).__init__()
        try:
            self.ui = uic.loadUi(uifile, self)
        except IOError:
            uifile = QtCore.QFile(":/ui/dashboard.ui")
            uifile.open(QtCore.QFile.ReadOnly)
            self.ui = uic.loadUi(uifile, self)
            uifile.close()

        self.actionAbout_pyhard2.triggered.connect(
            _partial(ControllerUi.aboutBox, self))

        self.graphicsScene = QtGui.QGraphicsScene(self.ui)
        self.graphicsView.setScene(self.graphicsScene)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.tabWidget.currentChanged.connect(self.fitInView)

    @Slot()
    def fitInView(self):
        if self.tabWidget.currentIndex() is 0:
            self.graphicsView.fitInView(self.graphicsScene.sceneRect())

    def resizeEvent(self, event):
        super(DashboardUi, self).resizeEvent(event)
        self.fitInView()


class Dashboard(QtCore.QObject):

    """Implement the behavior of the GUI.

    Methods:
        windowTitle()
        setWindowTitle(title)
            This property holds the window title (caption).
        show: Show the widget and its child widgets.
        close: Close the widget.
    """

    def __init__(self, uifile="", parent=None):
        super(Dashboard, self).__init__(parent)
        self.ui = DashboardUi(uifile)
        self._controllerPool = [self]
        self._widgetDataMonitor = []
        self._currentIndex = 0
        self.ui.tabWidget.currentChanged.connect(self._tabChanged)
        # methods
        self.windowTitle = self.ui.windowTitle
        self.setWindowTitle = self.ui.setWindowTitle
        self.show = self.ui.show
        self.close = self.ui.close

    def _addMonitorForSpinBox(self, item):
        def spinBox_valueChanged(value):
            plotCurve.data().append(value)
            plot.replot()

        plot = Qwt.QwtPlot(self.ui.plotHolder)
        plot.setTitle(item.toolTip())
        plot.setContextMenuPolicy(Qt.ActionsContextMenu)
        plot.setSizePolicy(QtGui.QSizePolicy.Preferred,
                           QtGui.QSizePolicy.Expanding)
        plot.hide()
        self._widgetDataMonitor.append(plot)
        self.ui.plotHolder.layout().addWidget(plot)
        plotCurve = Qwt.QwtPlotCurve()
        plotCurve.setData(TimeSeriesData())
        plotCurve.attach(plot)
        showMonitorAction = QtGui.QAction(u"monitor ...", item, checkable=True,
                                          toggled=plot.setVisible)
        plot.addAction(QtGui.QAction(u"hide", plot,
                                     triggered=showMonitorAction.toggle))
        plot.addAction(QtGui.QAction(u"clear", plot,
                                     triggered=plotCurve.data().clear))
        item.addAction(showMonitorAction)
        item.widget().valueChanged.connect(spinBox_valueChanged)

    def _connectSpinBoxToItem(self, spinBox, item, programmableColumn=None):
        def onItemChanged(item_):
            if item_ is item:
                spinBox.setValue(item.data())

        def onNewValueTriggered():
            item_ = item.model().item(item.row(), programmableColumn)
            value, ok = QtGui.QInputDialog.getDouble(
                self.ui.graphicsView,  # parent
                spinBox.toolTip(),  # title
                text,               # label
                value=item_.data(),
                min=item_.minimum() if item_.minimum()
                    is not None else 0.0,
                max=item_.maximum() if item_.maximum()
                    is not None else 99.0,
                decimals=2,)
            if ok:
                item_.setData(value)

        if item.minimum():
            spinBox.setMinimum(item.minimum())
        if item.maximum():
            spinBox.setMaximum(item.maximum())
        spinBox.setReadOnly(item.isReadOnly())
        spinBox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons
                                 if item.isReadOnly() else
                                 QtGui.QAbstractSpinBox.UpDownArrows)
        item.model().itemChanged.connect(onItemChanged)

        if programmableColumn is not None:
            text = item.model().horizontalHeaderItem(programmableColumn).text()
            newValueAction = QtGui.QAction("new %s" % text.lower(), spinBox,
                                           triggered=onNewValueTriggered)
            spinBox.addAction(newValueAction)
            doubleClickEventFilter = DoubleClickEventFilter(spinBox.lineEdit())
            doubleClickEventFilter.doubleClicked.connect(newValueAction.trigger)
            spinBox.lineEdit().installEventFilter(doubleClickEventFilter)

    def _connectButtonToItem(self, button, item):
        def onItemChanged(item_):
            if item_ is item:
                button.setChecked(item.data())

        button.setEnabled(not item.isReadOnly())
        model = item.model()
        model.itemChanged.connect(onItemChanged)
        button.clicked.connect(item.setData)

    def _tabChanged(self, new):
        controller = self._controllerPool[self._currentIndex]
        if controller is not self:
            controller.timer.timeout.disconnect(controller.replot)
        controller = self._controllerPool[new]
        if controller is not self:
            controller.replot()
            controller.timer.timeout.connect(controller.replot)
        self._currentIndex = new

    def _goToController(self, controller, row=None):
        self.ui.tabWidget.setCurrentIndex(
            self.ui.tabWidget.indexOf(controller.ui))
        if row is not None:
            controller.ui.driverView.selectRow(row)

    def mapToScene(self, point):
        rect = self.ui.graphicsScene.sceneRect()
        return QtCore.QPointF(rect.width() * point.x(),
                              rect.height() * point.y())

    def setBackgroundItem(self, backgroundItem):
        """Set the SVG image to use as a background."""
        backgroundItem.setParent(self.ui.graphicsScene)
        backgroundItem.setFlags(QtSvg.QGraphicsSvgItem.ItemClipsToShape)
        backgroundItem.setZValue(-1)
        self.ui.graphicsScene.addItem(backgroundItem)
        rect = backgroundItem.boundingRect()
        self.ui.graphicsScene.setSceneRect(0, 0, rect.width(), rect.height())
        self.ui.fitInView()

    def addSimpleText(self, text):
        """Add the `text` to the scene."""
        return self.ui.graphicsScene.addSimpleText(text)

    def addSceneItem(self, item):
        """Add the `item` to the scene."""

        def onContextMenuRequested(pos):
            # cannot use ActionsContextMenu as the menu scales
            # with the widget
            view = self.ui.graphicsView
            pos = view.viewport().mapToGlobal(
                view.mapFromScene(item.mapToScene(pos)))
            menu = QtGui.QMenu()
            menu.addActions(item.actions())
            menu.addActions(item.widget().actions())
            menu.exec_(pos)

        item.widget().setContextMenuPolicy(Qt.CustomContextMenu)
        item.widget().customContextMenuRequested.connect(onContextMenuRequested)
        item.setPos(self.mapToScene(item.pos()))
        self.ui.graphicsScene.addItem(item)

    def addController(self, controller):
        """Add the `controller` as a new tab."""
        controller.timer.timeout.disconnect(controller.replot)
        self.ui.menuWindow.addAction(QtGui.QAction(
            controller.windowTitle(), self.ui.menuWindow,
            triggered=lambda checked: self._goToController(controller)))
        self.ui.tabWidget.addTab(controller.ui, controller.windowTitle())
        self._controllerPool.append(controller)

    def addControllerAndWidgets(self, controller, proxyWidgetList):
        """Add a `controller` and its associated widgets."""
        self.addController(controller)
        for row, proxyWidget in enumerate(proxyWidgetList):
            self.addSceneItem(proxyWidget)
            column = 0
            modelItem = controller._driverModel.item(row, column)
            if not modelItem:
                logger.error(
                    "Size of configuration file and model do not match in %s" %
                    controller.windowTitle())
                continue
            proxyWidget.addAction(QtGui.QAction(
                u"go to controller...", proxyWidget,
                # needs early binding in the loop
                triggered=_partial(self._goToController, controller, row)))
            widget = proxyWidget.widget()
            if isinstance(widget, QtGui.QAbstractSpinBox):
                self._addMonitorForSpinBox(proxyWidget)
                self._connectSpinBoxToItem(widget, modelItem,
                                           controller.programmableColumn())
            elif isinstance(widget, QtGui.QAbstractButton):
                self._connectButtonToItem(widget, modelItem)
            else:
                raise NotImplementedError


def main(argv):
    app = QtGui.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    w = Dashboard()
    w.show()
    config = DashboardConfig(argv[1])
    config.parse()
    config.setupUi(w)
    sys.exit(app.exec_())


if __name__ == "__main__":
    import sys
    main(sys.argv)

