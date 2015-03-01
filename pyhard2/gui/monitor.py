"""Module with the `MonitorWidget` widget.

"""
from collections import defaultdict
from datetime import timedelta

from matplotlib import dates

from PyQt5 import QtWidgets, QtCore, QtGui
Qt = QtCore.Qt
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal

from pyhard2.gui.mpl import MplWidget


class MonitorWidgetUi(QtWidgets.QWidget):

    """The default UI for the monitor widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.headerLayout = QtWidgets.QHBoxLayout()
        self.historyLimitLabel = QtWidgets.QLabel("History limit", self)
        self.historyLimitCombo = QtWidgets.QComboBox(self)
        self.historyLimitCombo.addItem("30 min", timedelta(minutes=30))
        self.historyLimitCombo.addItem("1 h", timedelta(hours=1))
        self.historyLimitCombo.addItem("3 h", timedelta(hours=3))
        self.historyLimitCombo.addItem("6 h", timedelta(hours=6))
        self.historyLimitCombo.addItem("12 h", timedelta(hours=12))
        self.historyLimitCombo.addItem("24 h", timedelta(hours=24))
        self.historyLimitCombo.setCurrentIndex(3)
        self.headerLayout.addWidget(self.historyLimitLabel)
        self.headerLayout.addWidget(self.historyLimitCombo)
        self.verticalLayout.addLayout(self.headerLayout)
        self.monitor = MplWidget(self)
        self.axes = self.monitor.figure.add_subplot(111)
        self.axes.figure.autofmt_xdate()
        self.axes.xaxis.set_major_locator(dates.MinuteLocator())
        self.axes.xaxis.set_major_formatter(dates.DateFormatter("%d-%m %H:%M"))
        self.monitor.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.verticalLayout.addWidget(self.monitor)
        self.logScaleCB = QtWidgets.QCheckBox(self, text="Log scale")
        self.singleInstrumentCB = QtWidgets.QCheckBox(
            self,
            text="Single instrument")
        self.verticalLayout.addWidget(self.logScaleCB)
        self.verticalLayout.addWidget(self.singleInstrumentCB)


class MonitorWidget(MonitorWidgetUi):

    """The default widget for the monitor.

    .. image:: img/monitor.png

    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.driverModel = None
        self._monitorItems = defaultdict(list)

    def setDriverModel(self, driverModel):
        self.driverModel = driverModel

    def setSingleInstrument(self, row, state):
        """Monitor instrument at `row` iff `state`."""
        for row_, line in self._monitorItems.items():
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
    app = QtWidgets.QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    widget = MonitorWidget()
    widget.show()
    sys.exit(app.exec_())
