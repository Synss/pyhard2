"""Module with the `MonitorWidget` widget.

"""
import os
from collections import defaultdict
from itertools import chain
import csv
import time

import sip as _sip
for _type in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    _sip.setapi(_type, 2)

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal
import PyQt4.Qwt5 as Qwt


class ListData(Qwt.QwtData):

    """Custom `QwtData` mapping a list onto `x,y` values.

    """
    X, Y = range(2)

    def __init__(self):
        super(ListData, self).__init__()
        self._historySize = 10000
        self._history = []
        self._data = []
        # methods
        self.size = self.__len__

    def __len__(self):
        """Return length of data."""
        return len(self._history) + len(self._data)

    def __iter__(self):
        """Iterate on the data."""
        return iter(chain(self._history, self._data))

    def __getitem__(self, i):
        """Return `x,y` values at `i`."""
        try:
            return self._history[i]
        except IndexError:
            return self._data[i - len(self._history)]

    def sample(self, i):
        """Return `x,y` values at `i`."""
        return self[i]

    def copy(self):
        """Return self."""
        return self

    def historySize(self):
        """How many points of history to display after exportAndTrim."""
        return self._historySize

    def setHistorySize(self, historySize):
        """Set how many points of history to display after exportAndTrim."""
        self._historySize = historySize

    def x(self, i):
        """Return `x` value."""
        return self[i][ListData.X]

    def y(self, i):
        """Return `y` value."""
        return self[i][ListData.Y]

    def append(self, xy):
        """Add `x,y` values to the data.

        Does nothing if None is in `xy`.
        """
        if None in xy:
            return
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
        csv.writer(csvfile, delimiter="\t").writerows(currentData)


class TimeSeriesData(ListData):

    """A `ListData` to plot values against time.

    Note:
        The time is set to zero upon instantiation.

    """
    def __init__(self):
        super(TimeSeriesData, self).__init__()
        self.__start = time.time()

    def append(self, value):
        """Append `time, value` to the list."""
        super(TimeSeriesData, self).append(
            (time.time() - self.__start, value))


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


class MonitorWidgetUi(QtGui.QWidget):

    """The default UI for the monitor widget."""

    def __init__(self, parent=None):
        super(MonitorWidgetUi, self).__init__(parent)
        self.verticalLayout = QtGui.QVBoxLayout(self)
        self.headerLayout = QtGui.QHBoxLayout()
        self.autoSaveLabel = QtGui.QLabel(u"AutoSave:", self)
        self.autoSaveEdit = QtGui.QLineEdit(self, frame=False, readOnly=True)
        self.headerLayout.addWidget(self.autoSaveLabel)
        self.headerLayout.addWidget(self.autoSaveEdit)
        self.verticalLayout.addLayout(self.headerLayout)
        self.monitor = Qwt.QwtPlot(self)
        self.monitor.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.verticalLayout.addWidget(self.monitor)
        self.logScaleCB = QtGui.QCheckBox(self, text=u"Log scale")
        self.singleInstrumentCB = QtGui.QCheckBox(self,
                                                  text=u"Single instrument")
        self.verticalLayout.addWidget(self.logScaleCB)
        self.verticalLayout.addWidget(self.singleInstrumentCB)

        self.zoomer = PlotZoomer(self.monitor.canvas())


class MonitorWidget(MonitorWidgetUi):

    """The default widget for the monitor.

    .. image:: img/monitor.png

    """
    def __init__(self, parent=None):
        super(MonitorWidget, self).__init__(parent)
        self.driverModel = None
        self.data = defaultdict(TimeSeriesData)
        self._monitorItems = defaultdict(list)

        self.__initActions()

        self.logScaleCB.stateChanged.connect(self.setLogScale)

    def __initActions(self):
        self.zoomOutAction = QtGui.QAction(
            "Zoom out", self, triggered=self.zoomer.clearZoomStack)
        self.monitor.addAction(self.zoomOutAction)

    def setDriverModel(self, driverModel):
        self.driverModel = driverModel

    @Slot()
    def populate(self):
        """Called when the model has been populated.

        Initialize monitor items.

        """
        for item in self.driverModel:
            text = os.path.join(  # used in autoSave
                self.driverModel.verticalHeaderItem(item.row()).text(),
                self.driverModel.horizontalHeaderItem(item.column()).text())
            curve = Qwt.QwtPlotCurve(text)
            curve.setData(self.data[item])
            curve.attach(self.monitor)
            self._monitorItems[item.row()].append(curve)

    def setLogScale(self, state):
        """Change the scale of `dataPlot` to log or linear."""
        if state:
            scale = Qwt.QwtLog10ScaleEngine()
            scale.setAttribute(Qwt.QwtScaleEngine.Symmetric)
        else:
            scale = Qwt.QwtLinearScaleEngine()
        self.monitor.setAxisScaleEngine(0, scale)

    def setSingleInstrument(self, row, state):
        """Monitor instrument at `row` iff `state`."""
        for row_, curve in self._monitorItems.iteritems():
            self._setDataPlotCurveVisibilityForRow(
                row_, not state or row_ is row)
        self._setDataPlotCurvePenForRow(
            row, QtGui.QPen(Qt.black) if state else QtGui.QPen(Qt.red))
        self.draw()

    def _setDataPlotCurveZ(self, row, z):
        if row is -1:  # ignore invalid index
            return
        for curve in self._monitorItems[row]:
            curve.setZ(z)

    def _setDataPlotCurveVisibilityForRow(self, row, visible=True):
        if row is -1:  # ignore invalid index
            return
        for curve in self._monitorItems[row]:
            curve.setVisible(visible)

    def _setDataPlotCurvePenForRow(self, row, pen):
        if row is -1:  # ignore invalid index
            return
        for curve in self._monitorItems[row]:
            curve.setPen(pen)

    def setCurrentRow(self, current, previous):
        if self.singleInstrumentCB.isChecked():
            self._setDataPlotCurveVisibilityForRow(previous, False)
            self._setDataPlotCurveVisibilityForRow(current, True)
        self._setDataPlotCurveZ(previous, 20)
        self._setDataPlotCurvePenForRow(previous, QtGui.QPen(Qt.black))
        self._setDataPlotCurveZ(current, 21)
        self._setDataPlotCurvePenForRow(current, QtGui.QPen(Qt.red))
        self.monitor.replot()

    def draw(self):
        self.monitor.replot()


if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    widget = MonitorWidget()
    widget.show()
    sys.exit(app.exec_())
