"""Module with the classes used to communicate with the driver and display
the results in the `DriverWidget`.

"""
import logging

import sip as _sip
for _type in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    _sip.setapi(_type, 2)

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal

from pyhard2.gui.delegates import DoubleSpinBoxDelegate
import pyhard2.driver as drv


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

    def __init__(self, parent=None):
        super(DriverModel, self).__init__(parent)
        self.setItemPrototype(DriverItem())

    def __repr__(self):
        return "%s(parent=%r)" % (self.__class__.__name__, self.parent())

    def __iter__(self):
        """Iterate on items."""
        return (self.item(row, column)
                for row in range(self.rowCount())
                for column in range(self.columnCount()))

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


class DriverWidgetUi(QtGui.QWidget):

    """The default UI for the driver widget."""

    def __init__(self, parent=None):
        super(DriverWidgetUi, self).__init__(parent)
        self.verticalLayout = QtGui.QVBoxLayout(self)
        self.driverView = QtGui.QTableView(
            self,
            selectionMode=QtGui.QAbstractItemView.SingleSelection,
            selectionBehavior=QtGui.QAbstractItemView.SelectRows
        )
        self.driverView.setContextMenuPolicy(Qt.CustomContextMenu)
        hHeader = self.driverView.horizontalHeader()
        hHeader.setStretchLastSection(True)
        hHeader.setDefaultSectionSize(20)
        hHeader.setResizeMode(QtGui.QHeaderView.Stretch)
        hHeader.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        vHeader = self.driverView.verticalHeader()
        vHeader.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        self.verticalLayout.addWidget(self.driverView)
        self.pidBox = QtGui.QGroupBox("PID settings", self)
        self.pEditor = QtGui.QDoubleSpinBox(self)
        self.iEditor = QtGui.QDoubleSpinBox(self)
        self.dEditor = QtGui.QDoubleSpinBox(self)
        self.pidLayout = QtGui.QFormLayout(self.pidBox)
        self.pidLayout.addRow("Proportional", self.pEditor)
        self.pidLayout.addRow("Integral", self.iEditor)
        self.pidLayout.addRow("Derivative", self.dEditor)
        self.verticalLayout.addWidget(self.pidBox)

        self.pidBoxMapper = QtGui.QDataWidgetMapper(self.pidBox)
        self.pidBoxMapper.setSubmitPolicy(QtGui.QDataWidgetMapper.AutoSubmit)
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
        rightClickMenu = QtGui.QMenu(self.driverView)
        rightClickMenu.addActions(
            [QtGui.QAction(
                "Polling", self, checkable=True,
                checked=item.isPolling(), triggered=item.setPolling),
             QtGui.QAction(
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
    app = QtGui.QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    widget = DriverWidget()
    widget.show()
    sys.exit(app.exec_())
