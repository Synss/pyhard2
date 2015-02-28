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

from matplotlib.lines import Line2D
import numpy as np

from pyhard2.gui.mpl import MplWidget


class ListData(object):

    def __init__(self):
        self._historySize = 10000
        self._history = []
        self._data = []

    def __len__(self):
        """Return length of data."""
        return len(self._history) + len(self._data)

    def __iter__(self):
        """Iterate over the data."""
        return chain(self._history, self._data)

    def __getitem__(self, i):
        """Return value at `i`."""
        try:
            return self._history[i]
        except IndexError:
            return self._data[i - len(self._history)]

    def append(self, value):
        """Append `value` to the data."""
        self._data.append(value)

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

    def x(self):
        try:
            return np.array(self)[:,0]
        except IndexError:
            return np.array([])

    def y(self):
        try:
            return np.array(self)[:,1:]
        except IndexError:
            return np.array([])


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
        self.monitor = MplWidget(self)
        self.axes = self.monitor.figure.add_subplot(111)
        self.monitor.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.verticalLayout.addWidget(self.monitor)
        self.logScaleCB = QtGui.QCheckBox(self, text=u"Log scale")
        self.singleInstrumentCB = QtGui.QCheckBox(self,
                                                  text=u"Single instrument")
        self.verticalLayout.addWidget(self.logScaleCB)
        self.verticalLayout.addWidget(self.singleInstrumentCB)


class MonitorWidget(MonitorWidgetUi):

    """The default widget for the monitor.

    .. image:: img/monitor.png

    """
    def __init__(self, parent=None):
        super(MonitorWidget, self).__init__(parent)
        self.driverModel = None
        self.data = defaultdict(TimeSeriesData)
        self._monitorItems = defaultdict(list)

    def setDriverModel(self, driverModel):
        self.driverModel = driverModel

    @Slot()
    def populate(self):
        """Called when the model has been populated.

        Initialize monitor items.

        """

    def setSingleInstrument(self, row, state):
        """Monitor instrument at `row` iff `state`."""
        for row_, line in self._monitorItems.iteritems():
            self._setDataPlotCurveVisibilityForRow(
                row_, not state or row_ is row)
        self._setDataPlotCurvePenForRow(
            row, QtGui.QPen(Qt.black) if state else QtGui.QPen(Qt.red))
        self.draw()

    def _setDataPlotCurveZ(self, row, z):
        if row is -1:  # ignore invalid index
            return
        for line in self._monitorItems[row]:
            line.setZ(z)

    def _setDataPlotCurveVisibilityForRow(self, row, visible=True):
        if row is -1:  # ignore invalid index
            return
        for line in self._monitorItems[row]:
            line.setVisible(visible)

    def _setDataPlotCurvePenForRow(self, row, pen):
        if row is -1:  # ignore invalid index
            return
        for line in self._monitorItems[row]:
            line.setPen(pen)

    def setCurrentRow(self, current, previous):
        if self.singleInstrumentCB.isChecked():
            self._setDataPlotCurveVisibilityForRow(previous, False)
            self._setDataPlotCurveVisibilityForRow(current, True)
        #self._setDataPlotCurveZ(previous, 20)
        #self._setDataPlotCurvePenForRow(previous, QtGui.QPen(Qt.black))
        #self._setDataPlotCurveZ(current, 21)
        #self._setDataPlotCurvePenForRow(current, QtGui.QPen(Qt.red))
        self.monitor.draw()

    def draw(self):
        self.monitor.draw()


if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    widget = MonitorWidget()
    widget.show()
    sys.exit(app.exec_())
