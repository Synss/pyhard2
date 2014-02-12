""" Models for pyhard2.ctrlr.qt4 """

import time as _time
from functools import partial as _partial

from PyQt4 import QtCore, QtGui
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal
Qt = QtCore.Qt
import PyQt4.Qwt5 as Qwt

from pyhard2 import pid
import pyhard2.driver as drv  # for Adapter

from .enums import UserRole


class _CurveData(Qwt.QwtData):
    
    """
    Custom `QwtData` mapping a list onto `x,y` values.
    
    Notes
    -----
    The list is stored in the class.
    
    """
    X, Y = range(2)

    def __init__(self, xy):
        super(_CurveData, self).__init__()
        self.__data = xy

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
        return self.sample(i)[_CurveData.X]

    def y(self, i):
        """Return `y` value."""
        return self.sample(i)[_CurveData.Y]

    def append(self, xy):
        """Add `x,y` values to the list."""
        self.__data.append(xy)

    def clear(self):
        """Clear the list in place."""
        self.__data = []


class LoggingItem(QtGui.QStandardItem):

    """:class:`QtGui.StandardItem` remembering data history."""

    def __init__(self):
        super(LoggingItem, self).__init__()
        self.__start = _time.time()
        self.__data = _CurveData([])

    def loggedData(self):
        """Return logged data."""
        return self.__data

    def log(self, role=Qt.DisplayRole):
        """Log the value in `role`."""
        value = self.data(role)
        if value is not None:
            self.__data.append((_time.time() - self.__start, value))


class InstrumentItem(LoggingItem):

    """`LoggingItem` managing communication with the hardware."""

    def __init__(self, instrument=None):
        super(InstrumentItem, self).__init__()
        self.__instr = instrument
        self._connectedRole = Qt.EditRole

    def type(self):
        """Reimplemented from :class:`QtGui.QStandardItem`."""
        return self.UserType

    def clone(self):
        """Reimplemented from :class:`QtGui.QStandardItem`."""
        return self.__class__()

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

    """Model item handling setpoint ramps."""

    def __init__(self):
        super(SetpointItem, self).__init__()
        self.__profileModel = QtGui.QStandardItemModel(8, 2)
        self.__profileModel.setHorizontalHeaderLabels(
            u"time / s;setpoint".split(";"))
        self.__ramp = None
        self.__profile = None

    def profileModel(self):
        """Return the data model for the setpoint ramp."""
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
        self.model()._pollingTimer.timeout.connect(self._updateSetpoint)
        self.setCheckState(Qt.Checked)

    def stopRamp(self):
        """Stop the setpoint ramp.

        Notes
        -----
        The current value is kept in the model.

        """
        if self.__ramp is not None:
            self.model()._pollingTimer.timeout.disconnect(self._updateSetpoint)
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
        self.setItemPrototype(SetpointItem())

        self._threads = []
        self._pollingTimer = QtCore.QTimer(self)

        self.configLoaded.connect(self.startPolling)

        self._instrumentClass = {}

    def setPollingOnColumn(self, column, polling=True):
        """Set `PollingCheckStateRole` to `polling` for `column`."""
        self.horizontalHeaderItem(column).setData(
            polling, role=UserRole.PollingCheckStateRole)

    def pollingOnColumn(self, column):
        """Return `PollingCheckStateRole` for `column`."""
        return self.horizontalHeaderItem(column).data(
            role=UserRole.PollingCheckStateRole)

    def startPolling(self):
        """Start the polling timer."""
        self._pollingTimer.start()

    def stopPolling(self):
        """Stop polling timer."""
        self._pollingTimer.stop()

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
                    QtCore.QTimer.singleShot(0, item.enqueueData)
                    if (self.horizontalHeaderItem(ncol)
                            .data(role=UserRole.PollingCheckStateRole)):
                        self._pollingTimer.timeout.connect(item.enqueueData)
            thread.start()
            self._threads.append(thread)
        self._pollingTimer.start()
        self.configLoaded.emit()

    def closeEvent(self, event):
        """Reimplemented from `QtCore.QStandardItemModel`."""
        for thread in self._threads:
            thread.quit()
            thread.wait()
        self.stopPolling()
        super(InstrumentModel, self).closeEvent(event)


