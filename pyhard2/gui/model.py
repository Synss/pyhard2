"""The `DriverModel` class provides a high-level interface for reading
and writing commands in a driver.

The model has the form of a two-dimensional table where the horizontal
headers contain a :class:`~pyhard2.driver.Command` associated to a
column and the veritcal header contains the `node` to which the command
is addressed:

.. table:: Example with a simplified representation of the `DriverModel`
           to the :class:`~pyhard2.driver.pfeiffer.Maxigauge` driver.

    = ===============================  ================================
    \ ``Cmd("PR", access=Access.RO)``  ``Cmd("UNI", access=Access.RO)``
    = ===============================  ================================
    1 pressure at node 1               unit at node 1
    2 pressure at node 2               unit at node 2
    3 pressure at node 3               unit at node 3
    = ===============================  ================================


"""
import logging

from PyQt5 import QtCore, QtGui
Qt = QtCore.Qt
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal

from pyhard2.driver import HardwareError


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
        except HardwareError as e:
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
