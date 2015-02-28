"""Module with the `DriverWidget` widget.

"""
from PyQt5 import QtWidgets, QtCore
Qt = QtCore.Qt
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal

from pyhard2.gui.delegates import DoubleSpinBoxDelegate


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


class DriverWidgetUi(QtWidgets.QWidget):

    """The default UI for the driver widget."""

    def __init__(self, parent=None):
        super(DriverWidgetUi, self).__init__(parent)
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.driverView = QtWidgets.QTableView(
            self,
            selectionMode=QtWidgets.QAbstractItemView.SingleSelection,
            selectionBehavior=QtWidgets.QAbstractItemView.SelectRows
        )
        self.driverView.setContextMenuPolicy(Qt.CustomContextMenu)
        hHeader = self.driverView.horizontalHeader()
        hHeader.setStretchLastSection(True)
        hHeader.setDefaultSectionSize(20)
        hHeader.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        hHeader.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        vHeader = self.driverView.verticalHeader()
        vHeader.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.verticalLayout.addWidget(self.driverView)
        self.pidBox = QtWidgets.QGroupBox("PID settings", self)
        self.pEditor = QtWidgets.QDoubleSpinBox(self)
        self.iEditor = QtWidgets.QDoubleSpinBox(self)
        self.dEditor = QtWidgets.QDoubleSpinBox(self)
        self.pidLayout = QtWidgets.QFormLayout(self.pidBox)
        self.pidLayout.addRow("Proportional", self.pEditor)
        self.pidLayout.addRow("Integral", self.iEditor)
        self.pidLayout.addRow("Derivative", self.dEditor)
        self.verticalLayout.addWidget(self.pidBox)

        self.pidBoxMapper = QtWidgets.QDataWidgetMapper(self.pidBox)
        self.pidBoxMapper.setSubmitPolicy(
            QtWidgets.QDataWidgetMapper.AutoSubmit)
        self.pidBoxMapper.setItemDelegate(
            ItemRangedSpinBoxDelegate(parent=self.pidBoxMapper))


class DriverWidget(DriverWidgetUi):

    """The default widget to display results from `DriverModel`.

    .. image:: img/driver.png

    """
    def __init__(self, parent=None):
        super(DriverWidget, self).__init__(parent)
        self.driverModel = None
        self.driverView.setItemDelegate(
            ItemRangedSpinBoxDelegate(parent=self.driverView))
        self.driverView.customContextMenuRequested.connect(
            self._show_driverView_contextMenu)

    def _show_driverView_contextMenu(self, pos):
        column = self.driverView.columnAt(pos.x())
        row = self.driverView.rowAt(pos.y())
        item = self.model.item(row, column)
        rightClickMenu = QtWidgets.QMenu(self.driverView)
        rightClickMenu.addActions(
            [QtWidgets.QAction(
                "Polling", self, checkable=True,
                checked=item.isPolling(), triggered=item.setPolling),
             QtWidgets.QAction(
                 "Logging", self, checkable=True,
                 checked=item.isLogging(), triggered=item.setLogging)
             ])
        rightClickMenu.exec_(self.driverView.viewport().mapToGlobal(pos))

    def setDriverModel(self, driverModel):
        """Set `driverModel`."""
        self.driverModel = driverModel
        self.driverView.setModel(self.driverModel)
        self.pidBoxMapper.setModel(self.driverModel)

    @Slot()
    def populate(self):
        """Called when the model has been populated."""

    def mapPEditor(self, column):
        """Map PID P editor to column `column` of `driverModel`."""
        assert(self.driverModel)
        self.pidBoxMapper.addMapping(self.pEditor, column)

    def mapIEditor(self, column):
        """Map PID I editor to column `column` of `driverModel`."""
        assert(self.driverModel)
        self.pidBoxMapper.addMapping(self.iEditor, column)

    def mapDEditor(self, column):
        """Map PID D editor to column `column` of `driverModel`."""
        assert(self.driverModel)
        self.pidBoxMapper.addMapping(self.dEditor, column)


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    widget = DriverWidget()
    widget.show()
    sys.exit(app.exec_())
