""" Models for pyhard2.ctrlr.qt4 """

import time as _time
import csv as _csv
from functools import partial as _partial

from PyQt4 import QtCore, QtGui
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal
Qt = QtCore.Qt
import PyQt4.Qwt5 as Qwt

from pyhard2 import pid
import pyhard2.driver as drv  # for Adapter

from .enums import UserRole


class ListData(Qwt.QwtData):
    
    """
    Custom `QwtData` mapping a list onto `x,y` values.
    
    Notes
    -----
    The list is stored in the class.
    
    """
    X, Y = range(2)

    def __init__(self):
        super(ListData, self).__init__()
        self.__data = []

    def __iter__(self):
        return self.__data.__iter__()

    def copy(self):
        """Return self."""
        return self

    def size(self):
        """Return length of list."""
        return len(self.__data)

    def sample(self, i):
        """Return `x,y` values at `i`."""
        return self.__data[i]

    def x(self, i):
        """Return `x` value."""
        return self.sample(i)[ListData.X]

    def y(self, i):
        """Return `y` value."""
        return self.sample(i)[ListData.Y]

    def append(self, xy):
        """Add `x,y` values to the list.

        Does nothing if None is in `xy`.
        """
        if None in xy: return
        self.__data.append(xy)

    def clear(self):
        """Clear the list in place."""
        self.__data = []


class TimeSeriesData(ListData):
    """
    A `ListData` to plot values against time.

    """
    def __init__(self):
        super(TimeSeriesData, self).__init__()
        self.__start = _time.time()

    def append(self, value):
        """Add `time, value` values to the data."""
        super(TimeSeriesData, self).append(
            (_time.time() - self.__start, value))


class ColumnRangedItem(QtGui.QStandardItem):
    """
    Item that returns the minimum and maximum values for the column set
    in a `ColumnRangedModel`.

    """
    def __init__(self):
        super(ColumnRangedItem, self).__init__()

    def clone(self):
        return self.__class__()

    def minimum(self):
        """ Return this item's minimum value. """
        return self.model().minimumForColumn(self.column())

    def maximum(self):
        """ Return this item's maximum value. """
        return self.model().maximumForColumn(self.column())


class ColumnRangedModel(QtGui.QStandardItemModel):
    """
    Model that stores minimum and maximum values column-wise.

    """

    minimumRole = Qt.UserRole + 1
    maximumRole = Qt.UserRole + 2

    def __init__(self, rows, columns, parent=None):
        super(ColumnRangedModel, self).__init__(rows, columns, parent)
        self.setItemPrototype(ColumnRangedItem())

    def minimumForColumn(self, column):
        """ Return the minimum value for the items in `column`. """
        item = self.horizontalHeaderItem(column)
        return item.data(role=ColumnRangedModel.minimumRole)

    def setMinimumForColumn(self, column, minimum):
        """ Set the minimum value for the items in `column`. """
        item = self.horizontalHeaderItem(column)
        item.setData(minimum, role=ColumnRangedModel.minimumRole)

    def maximumForColumn(self, column):
        """ Return the maximum value for the items in `column`. """
        item = self.horizontalHeaderItem(column)
        return item.data(role=ColumnRangedModel.maximumRole)

    def setMaximumForColumn(self, column, maximum):
        """ Set the maximum value for the items in `column`. """
        item = self.horizontalHeaderItem(column)
        item.setData(maximum, role=ColumnRangedModel.maximumRole)


class InstrumentItem(QtGui.QStandardItem):

    """`StandardItem` managing communication with the hardware."""

    def __init__(self, instrument=None):
        super(InstrumentItem, self).__init__()
        self.__instr = instrument
        self._timeSeries = TimeSeriesData()
        self._connectedRole = Qt.EditRole

    def type(self):
        """Reimplemented from :class:`QtGui.QStandardItem`."""
        return self.UserType

    def clone(self):
        """Reimplemented from :class:`QtGui.QStandardItem`."""
        return self.__class__()

    def timeSeries(self):
        """Return logged data."""
        return self._timeSeries

    def instrument(self):
        """Return the `Instrument`."""
        return self.__instr

    def setInstrument(self, instrument):
        """Set this item's `instrument`."""
        self.__instr = instrument
        # unset ItemIsEditable if command is read-only on instrument
        item = self.model().horizontalHeaderItem(self.column())
        cmd = "%s_is_readonly" % item.data(role=UserRole.CommandName)
        readOnly = reduce(getattr, cmd.split("."), self.__instr)()
        if readOnly:
            self.setFlags(self.flags() ^ Qt.ItemIsEditable)

    def maximum(self):
        """Return this item's maximum value.

        The value is read in the driver"""
        item = self.model().horizontalHeaderItem(self.column())
        cmd = "%s_maximum" % item.data(role=UserRole.CommandName)
        return reduce(getattr, cmd.split("."), self.__instr)()

    def minimum(self):
        """Return this item's minimum value.

        The value is read in the driver."""
        item = self.model().horizontalHeaderItem(self.column())
        cmd = "%s_minimum" % item.data(role=UserRole.CommandName)
        return reduce(getattr, cmd.split("."), self.__instr)()

    def enqueueData(self):
        """
        Request reading data in hardware.
        
        Notes
        -----
        The value registered to the column is only requested here and
        cannot be accessed directly.  The value may be passed to
        the model at `role` if :meth:`connectHardware` has been called
        before.
        
        """
        if self.__instr:
            item = self.model().horizontalHeaderItem(self.column())
            cmd = "get_%s" % item.data(role=UserRole.CommandName)
            reduce(getattr, cmd.split("."), self.__instr)()

    def sendData(self, data):
        """Send data to the hardware."""
        if self.__instr and self.isEditable():
            item = self.model().horizontalHeaderItem(self.column())
            cmd = ("set_%s"
                   if item.data(role=UserRole.CommandType) == "Parameter"
                   else "do_%s") % item.data(role=UserRole.CommandName)
            reduce(getattr, cmd.split("."), self.__instr)(data)

    def connectHardware(self, role=Qt.EditRole):
        """
        Set the value returned from the hardware to `role` in the model.

        """
        if self.__instr:
            self._connectedRole = role
            item = self.model().horizontalHeaderItem(self.column())
            cmd = "%s_signal" % item.data(role=UserRole.CommandName)
            reduce(getattr, cmd.split("."), self.__instr)().connect(
                _partial(self.setData, role=role))

    def setData(self, value, role=Qt.UserRole + 1):
        super(InstrumentItem, self).setData(value, role)
        if role == self._connectedRole:
            self.sendData(value)


class SetpointItem(InstrumentItem):

    """ `InstrumentItem` handling setpoint ramps. """

    def __init__(self):
        super(SetpointItem, self).__init__()
        self.__profileModel = ColumnRangedModel(8, 2)
        self.__profileModel.setHorizontalHeaderLabels(
            u"time / s;setpoint".split(";"))
        self.__profileModel.setMinimumForColumn(0, 0)
        self.__profileModel.setMaximumForColumn(0, 36000)
        self.__profileModel.setMinimumForColumn(1, 0)
        self.__profileModel.setMaximumForColumn(1, 99)
        self.__ramp = None
        self.__profile = None

    def profileModel(self):
        """Return the data model for the setpoint ramp."""
        self.__profileModel.setMinimumForColumn(1, self.minimum())
        self.__profileModel.setMaximumForColumn(1, self.maximum())
        return self.__profileModel

    def startRamp(self):
        """Start setpoint ramp."""
        model = self.profileModel()

        profile = []
        for nrow in range(model.rowCount()):
            time = model.item(nrow, 0)
            setp = model.item(nrow, 1)
            if None in (time, setp): continue
            profile.append((time.data(Qt.DisplayRole),
                            setp.data(Qt.DisplayRole)))

        self.__profile = pid.Profile(profile)
        self.__ramp = self.__profile.ramp()
        self.model().polling.connect(self._updateSetpoint)
        self.setCheckState(Qt.Checked)

    def stopRamp(self):
        """Stop the setpoint ramp.

        Notes
        -----
        The current value is kept in the model.

        """
        if self.__ramp is not None:
            self.model().polling.disconnect(self._updateSetpoint)
        self.setCheckState(Qt.Unchecked)
        self.__ramp = None
        self.__profile = None

    def isRampRunning(self):
        """Return whether the ramp is in progress."""
        return self.checkState() == Qt.Checked

    def _updateSetpoint(self):
        """Update the setpoint."""
        if self.__profile is None:
            return
        try:
            setpoint = self.__ramp.next()
        except StopIteration:
            setpoint = self.__profile.profile[-1][self.__profile.SP]
            self.stopRamp()
        self.setData(setpoint, role=Qt.EditRole)


class InstrumentModel(QtGui.QStandardItemModel):

    """
    A model that can hold instruments.
    """

    configLoaded = Signal()
    """Signal to signify the view that it should adapt itself to the
    config file."""

    def __init__(self, parent=None):
        super(InstrumentModel, self).__init__(parent)
        self.setItemPrototype(InstrumentItem())
        self.configLoaded.connect(self._populateModel)
        self._threads = []
        self._instrumentClass = {}

    def registerParameter(self, column, paramName):
        """Register `paramName` as the `Parameter` for `column`.
        
        Registering a new `Parameter` removes commands already
        registered for this column.
        """
        self.horizontalHeaderItem(column).setData(
            paramName, role=UserRole.CommandName)
        self.horizontalHeaderItem(column).setData(
            "Parameter", role=UserRole.CommandType)

    def registerAction(self, column, actionName):
        """Register `actionName` as the `Action` for `column`.

        Registering a new `Action` removes commands already registered
        for this column.
        """
        self.horizontalHeaderItem(column).setData(
            actionName, role=UserRole.CommandName)
        self.horizontalHeaderItem(column).setData(
            "Action", role=UserRole.CommandType)

    def addInstrumentClass(self, instrCls, name=None, mapper=None):
        """Register instrument class with the model.
        
        Parameters
        ----------
        instrCls : `Instrument`
        name : text, optional
            Default to `instrCls.__name__`.
        mapper : dict
            Mapper for the :class:`pyhard2.driver.DriverAdapter`.
        
        """
        if mapper is None:
            labels = [str(self.headerData(ncol, Qt.Horizontal))
                      for ncol in range(self.columnCount())]
            mapper = dict(zip(labels, labels))
        if name is None:
            name = instrCls.__name__
        self._instrumentClass[name] = (instrCls, mapper)

    def _populateModel(self):
        for item in (self.itemFromIndex(self.index(row, column))
                     for row in range(self.rowCount())
                     for column in range(self.columnCount())):
            item.enqueueData()

    def loadConfig(self, opts):
        """Populate the model.

        This method assumes that there can be several instruments per 
        socket and each socket goes in its own thread.

        Emit the configLoaded signal to signify the view that it may
        display the contents of the model.

        Parameters
        ----------
        opts : `utils.cmdline`
            Commandline options.

        """
        for port in opts.config:
            ser = drv.Serial()
            ser.port = port
            if not opts.virtual:
                try:
                    ser.open()
                except drv.serial.SerialException:
                    pass
            thread = QtCore.QThread(self)
            for nrow, conf in enumerate(opts.config[port]):
                driverCls, mapper = self._instrumentClass[conf["driver"]]
                self.setVerticalHeaderItem(
                    nrow, QtGui.QStandardItem(conf.get("name", "%i" % nrow)))
                restArgs = conf.get("extra", {})
                adapter = drv.DriverAdapter(driverCls(ser, async=True,
                                                      **restArgs), mapper)
                adapter.moveToThread(thread)
                for ncol in range(self.columnCount()):
                    item = self.itemFromIndex(self.index(nrow, ncol))
                    item.setInstrument(adapter)
                    item.connectHardware()
            thread.start()
            self._threads.append(thread)
        self.configLoaded.emit()

    def closeEvent(self, event):
        """Reimplemented from `QtCore.QStandardItemModel`."""
        for thread in self._threads:
            thread.quit()
            thread.wait()
        super(InstrumentModel, self).closeEvent(event)


class PollingInstrumentModel(InstrumentModel):

    """ `InstrumentModel` that handles polling its items' `enqueueData`. """

    polling = Signal()

    def __init__(self, parent=None):
        super(PollingInstrumentModel, self).__init__(parent)
        self.setItemPrototype(SetpointItem())
        self.__timer = QtCore.QTimer(self)
        self.__timer.timeout.connect(self.polling.emit)
        self.configLoaded.connect(self._connectPolling)
        self.configLoaded.connect(self._connectLogging)
        self.configLoaded.connect(self.__timer.start)

    def _connectPolling(self):
        def poll(item):
            headerItem = self.horizontalHeaderItem(item.column())
            if headerItem.data(role=UserRole.PollingCheckStateRole):
                item.enqueueData()

        for item in (self.itemFromIndex(self.index(row, column))
                     for row in range(self.rowCount())
                     for column in range(self.columnCount())):
            self.__timer.timeout.connect(_partial(poll, item))

    def _connectLogging(self):
        def log(item):
            headerItem = self.horizontalHeaderItem(item.column())
            if headerItem.data(role=UserRole.LoggingCheckStateRole):
                item.timeSeries().append(item.data(role=item._connectedRole))

        for item in (self.itemFromIndex(self.index(row, column))
                     for row in range(self.rowCount())
                     for column in range(self.columnCount())):
            self.__timer.timeout.connect(_partial(log, item))

    def setPollingOnColumn(self, column, polling=True):
        """Set `PollingCheckStateRole` to `polling` for `column`."""
        self.horizontalHeaderItem(column).setData(
            polling, role=UserRole.PollingCheckStateRole)

    def pollingOnColumn(self, column):
        """Return `PollingCheckStateRole` for `column`."""
        return self.horizontalHeaderItem(column).data(
            role=UserRole.PollingCheckStateRole) is True

    def setLoggingOnColumn(self, column, logging=True):
        """Set `LoggingCheckStateRole` to `logging` for `column`."""
        self.horizontalHeaderItem(column).setData(
            logging, role=UserRole.LoggingCheckStateRole)

    def loggingOnColumn(self, column):
        """Return `LoggingCheckStateRole` for `column`."""
        return self.horizontalHeaderItem(column).data(
            role=UserRole.LoggingCheckStateRole) is True

    def setInterval(self, interval):
        """Set polling/logging `interval`."""
        self.__timer.setInterval(interval)

    def interval(self):
        """Return polling/logging `interval`."""
        return self.__timer.interval()

    def closeEvent(self, event):
        self.__timer.stop()
        super(InstrumentModel, self).closeEvent(event)


