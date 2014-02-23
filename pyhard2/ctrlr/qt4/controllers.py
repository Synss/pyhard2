""" Controllers for pyhard2.ctrlr.qt4 """

from functools import partial

from PyQt4 import QtCore, QtGui
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal
Qt = QtCore.Qt

import PyQt4.Qwt5 as Qwt

from .widgets import Spreadsheet, Monitor, Curve, MeasureEdit
from .delegates import NumericDelegate
from .models import InstrumentModel
from .enums import ColumnName


class _StartProgramDelegate(QtGui.QAbstractItemDelegate):

    """Helper class for Controller._startProgramMapper."""

    def __init__(self, parent=None):
        super(_StartProgramDelegate, self).__init__(parent)

    def setEditorData(self, editor, index):
        """Set editor's checked state."""
        if not index.isValid():
            return
        editor.setChecked(Qt.Unchecked
                          if not index.data(role=Qt.CheckStateRole) else
                          index.data(role=Qt.CheckStateRole))
        editor.setIcon(QtGui.QIcon.fromTheme(
            "media-playback-stop" if editor.isChecked() else
            "media-playback-start",
            QtGui.QIcon(":/icons/Tango/media-playback-stop.svg"
                        if editor.isChecked() else
                        ":/icons/Tango/media-playback-start.svg")))

    def setModelData(self, editor, model, index):
        """Start or stop ramp according to editor's check state."""
        if not index.isValid():
            return
        setpointItem = model.itemFromIndex(index)
        # ignore
        # - ramp running + button pressed
        # - ramp stopped + button released
        if editor.isChecked() and not setpointItem.isRampRunning():
            setpointItem.startRamp()
        elif not editor.isChecked() and setpointItem.isRampRunning():
            setpointItem.stopRamp()


class _ProgramTableDelegate(QtGui.QAbstractItemDelegate):

    """Helper class for Controller._profileModelMapper."""

    def __init__(self, parent=None):
        super(_ProgramTableDelegate, self).__init__(parent)

    def setEditorData(self, editor, index):
        """Set editor's model to `profileModel` at `index`."""
        if not index.isValid():
            return
        item = index.model().itemFromIndex(index)
        editor.setModel(item.profileModel())


class _NumericRangeDelegate(NumericDelegate):

    def __init__(self, parent=None):
        super(_NumericRangeDelegate, self).__init__(parent)
        self._minimum = 0.0
        self._maximum = 99.0

    def setMinimum(self, minimum):
        self._minimum = minimum

    def minimum(self):
        return self._minimum

    def setMaximum(self, maximum):
        self._maximum = maximum

    def maximum(self):
        return self._maximum

    def setRange(self, minimum, maximum):
        self.setMinimum(minimum)
        self.setMaximum(maximum)

    def range(self):
        return self.minimum, self.maximum

    def createEditor(self, parent, option, index):
        if index.isValid():
            editor = super(_NumericRangeDelegate, self).createEditor(
                parent, option, index)
            editor.setrange(self.range())
            return editor
        else:
            return super(_NumericRangeDelegate, self).createEditor(
                parent, option, index)


class _InstrumentItemDelegate(NumericDelegate):

    """Helper class for Controller instrument table."""

    def __init__(self, parent=None):
        super(_InstrumentItemDelegate, self).__init__(parent)

    def createEditor(self, parent, option, index):
        """Set editor's min/max values from the values in the driver."""
        if index.isValid():
            editor = super(_InstrumentItemDelegate, self).createEditor(
                parent, option, index)
            item = index.model().itemFromIndex(index)
            minimum, maximum = item.minimum(), item.maximum()
            if minimum is not None:
                editor.setMinimum(minimum)
            if maximum is not None:
                editor.setMaximum(maximum)
            return editor
        else:
            return super(_InstrumentItemDelegate, self).createEditor(
                parent, option, index)


class _ModelData(Qwt.QwtData):

    """
    Custom `QwtData` mapping a model onto `x,y` values.
    
    """
    X, Y = range(2)

    def __init__(self, model, xColumn=0, yColumn=1):
        super(_ModelData, self).__init__()
        self.__model = model
        self.__xColumn = xColumn
        self.__yColumn = yColumn

    def model(self):
        """Return the model."""
        return self.__model

    def copy(self):
        """Return self."""
        return self

    def size(self):
        """Return the length of the model."""
        size = 0
        for nRow in range(self.__model.rowCount()):
            x = self.__model.item(nRow, self.__xColumn)
            y = self.__model.item(nRow, self.__yColumn)
            if None not in (x, y):
                size += 1
        return size

    def sample(self, i):
        """Return `x,y` values at `i`."""
        xItem, yItem = (self.__model.item(i, column)
                        for column in (self.__xColumn, self.__yColumn))
        if None in (xItem, yItem):
            return (0.0, 0.0)
        else:
            return map(float, (xItem.text(), yItem.text()))

    def x(self, i):
        """Return `x` value."""
        return self.sample(i)[_ModelData.X]

    def y(self, i):
        """Return `y` value."""
        return self.sample(i)[_ModelData.Y]


class Controller(QtGui.QMainWindow):
    """
    User interface to the controllers.

    Attributes
    ----------
    singleInstrumentAction : QtGui.QAction
    showPidBoxAction : QtGui.QAction
    showMonitorAction : QtGui.QAction
    showProgramBoxAction : QtGui.QAction
    startProgramAction : QtGui.QAction
    startAllProgramsAction : QtGui.QAction
    stopAllProgramsAction : QtGui.QAction

    """
    def __init__(self, parent=None):
        super(Controller, self).__init__(parent)
        centralWidget = QtGui.QWidget()
        centralWidget.setLayout(QtGui.QHBoxLayout())
        self.setCentralWidget(centralWidget)
        self.__loggingCurves = []  # prevent garbage collection
        self.__previewCurves = []  # prevent garbage collection
        self.__initInstrPane()
        self.__initMonitorPane()
        self.__initProgramPane()
        self.__initMenuBar()
        self._setModel()

    def __repr__(self):
        return "%s(parent=%r)" % (self.__class__.__name__, self.parent())

    def __initMenuBar(self):
        self._viewMenu = QtGui.QMenu(u"View", self.menuBar())
        self.menuBar().addMenu(self._viewMenu)

        self.singleInstrumentAction = QtGui.QAction(u"single instrument",
                                                     self._viewMenu)
        self.singleInstrumentAction.setCheckable(True)
        self.singleInstrumentAction.triggered.connect(
            self._controlBox.setVisible)
        self.singleInstrumentAction.triggered.connect(
            self._instrTable.setHidden)
        self._viewMenu.addAction(self.singleInstrumentAction)

        self.showPidBoxAction = QtGui.QAction(u"show PID", self._viewMenu)
        self.showPidBoxAction.setCheckable(True)
        self.showPidBoxAction.setChecked(True)
        self.showPidBoxAction.triggered.connect(self._pidBox.setVisible)
        self._viewMenu.addAction(self.showPidBoxAction)

        self.showMonitorAction = (
                QtGui.QAction(u"show monitor", self._viewMenu))
        self.showMonitorAction.setCheckable(True)
        self.showMonitorAction.setChecked(True)
        self.showMonitorAction.triggered.connect(self._monitorPane.setVisible)
        self._viewMenu.addAction(self.showMonitorAction)

        self.showProgramBoxAction = (
                QtGui.QAction(u"show program", self._viewMenu))
        self.showProgramBoxAction.setCheckable(True)
        self.showProgramBoxAction.setChecked(True)
        self.showProgramBoxAction.triggered.connect(self._programPane.setVisible)
        self._viewMenu.addAction(self.showProgramBoxAction)

    def __initInstrPane(self):
        self._instrPane = QtGui.QWidget(self)
        paneLayout = QtGui.QVBoxLayout(self._instrPane)
        self.centralWidget().layout().addWidget(self._instrPane)

        self._refreshRateCtrl = QtGui.QDoubleSpinBox()
        self._refreshRateCtrl.setRange(0.1, 3600.0)
        self._refreshRateCtrl.setValue(10.0)
        formLayout = QtGui.QFormLayout()
        formLayout.addRow(QtGui.QLabel(u"Refresh /s"), self._refreshRateCtrl)
        paneLayout.addLayout(formLayout)

        self._instrTable = QtGui.QTableView(self)
        self._instrTable.setItemDelegate(
            _InstrumentItemDelegate(self._instrTable))
        self._instrTable.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.Stretch)
        self._instrTable.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self._instrTable.verticalHeader().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        paneLayout.addWidget(self._instrTable)

        self._controlBox = QtGui.QGroupBox(u"Controls")
        self._controlBox.hide()
        controlBoxLayout = QtGui.QFormLayout(self._controlBox)
        paneLayout.addWidget(self._controlBox)

        self._pidBox = QtGui.QGroupBox(u"PID settings")
        paneLayout.addWidget(self._pidBox)
        pidBoxLayout = QtGui.QFormLayout(self._pidBox)
        self._pEditor = QtGui.QDoubleSpinBox(self._pidBox)
        self._iEditor = QtGui.QDoubleSpinBox(self._pidBox)
        self._dEditor = QtGui.QDoubleSpinBox(self._pidBox)
        pidBoxLayout.addRow(QtGui.QLabel(u"Proportional"), self._pEditor)
        pidBoxLayout.addRow(QtGui.QLabel(u"Integral"), self._iEditor)
        pidBoxLayout.addRow(QtGui.QLabel(u"Derivative"), self._dEditor)

        self._pidMapper = QtGui.QDataWidgetMapper(self._instrTable)
        self._pidMapper.setSubmitPolicy(self._pidMapper.AutoSubmit)
        self._pidMapper.setItemDelegate(NumericDelegate(self._pidMapper))

    def __initMonitorPane(self):
        self._monitorPane = QtGui.QWidget(self)
        paneLayout = QtGui.QVBoxLayout(self._monitorPane)
        self.centralWidget().layout().addWidget(self._monitorPane)

        self._monitor = Monitor(self)
        paneLayout.addWidget(self._monitor)

    def __initProgramPane(self):
        self._programPane = QtGui.QGroupBox(u"Program", self)
        self._programPane.setSizePolicy(QtGui.QSizePolicy.Fixed,
                                        QtGui.QSizePolicy.Expanding)
        programPaneLayout = QtGui.QVBoxLayout(self._programPane)

        self.centralWidget().layout().addWidget(self._programPane)

        self._programToolBar = QtGui.QToolBar(self._programPane)
        programPaneLayout.addWidget(self._programToolBar)

        self.startProgramAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "media-playback-start",
                QtGui.QIcon(":/icons/Tango/media-playback-start.svg")),
            u"Start program", self._programPane)
        self.startProgramAction.setCheckable(True)
        self._startProgramBtn = QtGui.QToolButton(self._programToolBar)
        self._startProgramBtn.setDefaultAction(self.startProgramAction)
        self._programToolBar.addWidget(self._startProgramBtn)

        self._startProgramMapper = QtGui.QDataWidgetMapper(self._instrTable)
        self._startProgramMapper.setSubmitPolicy(
            self._startProgramMapper.AutoSubmit)
        self._startProgramMapper.setItemDelegate(_StartProgramDelegate(
            self._startProgramMapper))

        self.startAllProgramsAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "media-seek-forward",
                QtGui.QIcon(":/icons/Tango/media-seek-forward.svg")),
            u"Start all programs", self._programPane)
        self.startAllProgramsAction.triggered.connect(self._startAllPrograms)
        self._startAllProgramsBtn = QtGui.QToolButton(self._programToolBar)
        self._startAllProgramsBtn.setDefaultAction(
            self.startAllProgramsAction)
        self._programToolBar.addWidget(self._startAllProgramsBtn)

        self.stopAllProgramsAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "process-stop",
                QtGui.QIcon(":/icons/Tango/process-stop.svg")),
            u"Stop all programs", self._programPane)
        self.stopAllProgramsAction.triggered.connect(self._stopAllPrograms)
        self._stopAllProgramsBtn = QtGui.QToolButton(self._programToolBar)
        self._stopAllProgramsBtn.setDefaultAction(self.stopAllProgramsAction)
        self._programToolBar.addWidget(self._stopAllProgramsBtn)

        self._programTable = Spreadsheet(self._programPane)
        self._programTable.verticalHeader().setDefaultSectionSize(20)
        self._programTable.horizontalHeader().setResizeMode(
            QtGui.QHeaderView.Stretch)
        self._programTable.horizontalHeader().setResizeMode(0,
            QtGui.QHeaderView.ResizeToContents)

        self._profileModelMapper = QtGui.QDataWidgetMapper(self._instrTable)
        self._profileModelMapper.setSubmitPolicy(
            self._profileModelMapper.AutoSubmit)
        self._profileModelMapper.setItemDelegate(
            _ProgramTableDelegate(self._profileModelMapper))

        self._programToolBar.addSeparator()

        self._copyProgramBtn = QtGui.QToolButton(self._programToolBar)
        self._copyProgramBtn.setDefaultAction(self._programTable.copyAction)
        self._programToolBar.addWidget(self._copyProgramBtn)

        self._pasteProgramBtn = QtGui.QToolButton(self._programToolBar)
        self._pasteProgramBtn.setDefaultAction(self._programTable.pasteAction)
        self._programToolBar.addWidget(self._pasteProgramBtn)

        self._programToolBar.addSeparator()

        self._addRowProgramBtn = QtGui.QToolButton(self._programToolBar)
        self._addRowProgramBtn.setDefaultAction(self._programTable.addRowAction)
        self._programToolBar.addWidget(self._addRowProgramBtn)

        self._removeRowProgramBtn = QtGui.QToolButton(self._programToolBar)
        self._removeRowProgramBtn.setDefaultAction(
            self._programTable.removeRowAction)
        self._programToolBar.addWidget(self._removeRowProgramBtn)

        timeDelegate = _NumericRangeDelegate(self._programTable)
        timeDelegate.setRange(0.0, 7.0 * 24.0 * 3600.0)  # 7 days
        self._programTable.setItemDelegateForColumn(0, timeDelegate)
        setpointDelegate = NumericDelegate(self._programTable)
        self._programTable.setItemDelegateForColumn(1, setpointDelegate)
        programPaneLayout.addWidget(self._programTable, 3)

        self._programPreview = Qwt.QwtPlot(self._programPane)
        programPaneLayout.addWidget(self._programPreview, 2)

    def _setModel(self, model=None):
        if model is None:
            model = InstrumentModel(self)
        model.configLoaded.connect(self.updateInstrumentTable)
        self._instrTable.setModel(model)

        model._pollingTimer.setInterval(self._refreshRateCtrl.value() * 1000)
        self._refreshRateCtrl.valueChanged.connect(
            lambda dt: model._pollingTimer.setInterval(1000 * dt))
        model._pollingTimer.timeout.connect(self._monitor.replot)

        self._pidMapper.setModel(model)
        self._instrTable.selectionModel().currentRowChanged.connect(
            self._pidMapper.setCurrentModelIndex)
        for editor, column in (
                (self._pEditor, ColumnName.PidGainColumn),
                (self._iEditor, ColumnName.PidIntegralColumn),
                (self._dEditor, ColumnName.PidDerivativeColumn)):
            self._pidMapper.addMapping(editor, column)
        model.configLoaded.connect(self._pidMapper.toFirst)

        self._profileModelMapper.setModel(model)
        self._instrTable.selectionModel().currentRowChanged.connect(
            self._profileModelMapper.setCurrentModelIndex)
        self._profileModelMapper.addMapping(
            self._programTable, ColumnName.SetpointColumn)

        self._startProgramMapper.setModel(model)
        self._instrTable.selectionModel().currentRowChanged.connect(
            self._startProgramMapper.setCurrentModelIndex)
        self._startProgramMapper.addMapping(self._startProgramBtn,
                                            ColumnName.SetpointColumn)
        self.startProgramAction.toggled.connect(
            self._startProgramMapper.submit)
        model.configLoaded.connect(self._startProgramMapper.toFirst)

    def previewCurves(self, column=ColumnName.SetpointColumn):
        model = self._instrTable.model()
        for row in range(model.rowCount()):
            label = model.verticalHeaderItem(row).text()
            previewCurve = Curve(label)
            item = model.item(row, column)
            profileModel = (item.profileModel() if item
                            else QtGui.QStandardItemModel(self))
            previewCurve.setData(_ModelData(profileModel))
            yield previewCurve

    def _startAllPrograms(self, checked, column=ColumnName.SetpointColumn):
        """Start every program stored in this controller."""
        model = self._instrTable.model()
        for nRow in range(model.rowCount()):
            spItem = model.item(nRow, column)
            if spItem:
                spItem.startRamp()

    def _stopAllPrograms(self, checked, column=ColumnName.SetpointColumn):
        """Stop every running program stored in this controller."""
        model = self._instrTable.model()
        for nRow in range(model.rowCount()):
            spItem = model.item(nRow, column)
            if spItem:
                spItem.stopRamp()

    def _previewPrograms(self, column=ColumnName.SetpointColumn):
        """Show a graphical preview of the programs."""
        previewWindow = QtGui.QWidget()
        previewWindow.setLayout(QtGui.QVBoxLayout(previewWindow))
        monitor = Qwt.QwtPlot(previewWindow)
        for previewCurve in self.previewCurves():
            previewCurve.attach(monitor)
        previewWindow.show()

    def instrumentTable(self):
        """Return table containing the instruments."""
        return self._instrTable

    def createEditor(self, row, column=ColumnName.MeasureColumn):
        """
        Return editor for an item of the `instrumentTable` at `row` and
        `column`.
        
        """
        def updateEditor(item):
            if (item.column() == column and item.row() == row):
                editor.setValue(item.data(role=Qt.DisplayRole))

        model = self._instrTable.model()
        editor = MeasureEdit()
        item = model.item(row, column)
        minimum, maximum = item.minimum(), item.maximum()
        if minimum is not None:
            editor.setMinimum(minimum)
        if maximum is not None:
            editor.setMaximum(maximum)
        editor.setCurveData(item.loggedData())
        model.itemChanged.connect(updateEditor)
        model.itemChanged.connect(editor.monitor().replot)

        if (column is ColumnName.MeasureColumn and
                model.columnCount() - 1 >= ColumnName.SetpointColumn):
            editor.enableSetpointAction(True)
            editor.setpointValue.connect(
                partial(model.item(row, ColumnName.SetpointColumn).setData,
                        role=Qt.EditRole))

        return editor

    def addInstrumentClass(self, instrCls, name=None, mapper=None):
        """Add instrument class to the controller."""
        self._instrTable.model().addInstrumentClass(instrCls, name, mapper)

    def loadConfig(self, opts):
        """Load config file into the controller."""
        self._instrTable.model().loadConfig(opts)

    def updateInstrumentTable(self):
        """
        Set up the instrument table according to the model currently loaded.

        """
        model = self._instrTable.model()
        for nCol in range(model.columnCount()):
            if self._instrTable.isColumnHidden(nCol):
                continue
            label = model.headerData(nCol, Qt.Horizontal)
            editor = QtGui.QDoubleSpinBox(self._controlBox)
            editor.setReadOnly(not model.item(0, nCol).isEditable())
            self._controlBox.layout().addRow(QtGui.QLabel(label), editor)

        for previewCurve in self.previewCurves():
            previewCurve.attach(self._programPreview)
            self.__previewCurves.append(previewCurve)

            marker = Qwt.QwtPlotMarker()
            marker.setLabel(previewCurve.title())
            marker.attach(self._programPreview)
            previewCurve.data().model().dataChanged.connect(
                partial(self._updateProgramPreview, marker, previewCurve))

        for nRow in range(model.rowCount()):
            for nCol in range(model.columnCount()):
                loggingCurve = Curve()
                item = model.item(nRow, nCol)
                loggingCurve.setData(item.loggedData())
                loggingCurve.attach(self._monitor)
                model._pollingTimer.timeout.connect(item.log)
                self.__loggingCurves.append(loggingCurve)

    def _updateProgramPreview(self, marker, curve):
        """Update program preview."""
        data = curve.data()
        x, y = (0.5 * (sample(data.size() - 2) + sample(data.size() - 1))
                for sample in (data.x, data.y))
        marker.setValue(x, y)
        curve.plot().replot()


class MeasureController(Controller):
    """
    Controller with a single table.

    The instrument table contains a single column registered to the
    parameter `measure`.

    .. image::  ../documentation/Controller.png

    """
    def __init__(self, parent=None):
        super(MeasureController, self).__init__(parent)

        model = self.instrumentTable().model()
        model.insertColumn(0)
        model.setHorizontalHeaderItem(ColumnName.MeasureColumn,
                                      QtGui.QStandardItem(u"measure"))
        model.registerParameter(ColumnName.MeasureColumn, "measure")
        model.setPollingOnColumn(ColumnName.MeasureColumn)        

        self.showPidBoxAction.trigger()
        self.showMonitorAction.trigger()
        self.showProgramBoxAction.trigger()


class MonitorController(MeasureController):
    """
    Controller with measure reading and a monitor.

    The instrument table contains a single column registered to the
    parameter `measure`.

    .. image:: ../documentation/MonitorController.png

    """
    def __init__(self, parent=None):
        super(MonitorController, self).__init__(parent)

        self.showMonitorAction.trigger()


class SetpointController(MonitorController):
    """
    Controller with measure and setpoint reading, includes PID
    controller and ramps.

    The instrument table contains eight columns registered to the
    parameters `measure`, `setpoint`, `output`, `PID gain`, `PID
    integral`, and `PID derivative`.

    .. image:: ../documentation/MonitorSetpointController.png

    """
    def __init__(self, parent=None):
        super(SetpointController, self).__init__(parent)

        model = self.instrumentTable().model()
        model.insertColumns(model.columnCount(), 5)

        for column, name in (
                (ColumnName.SetpointColumn, u"setpoint"),
                (ColumnName.OutputColumn, u"output"),
                (ColumnName.PidGainColumn, u"pid_gain"),
                (ColumnName.PidIntegralColumn, u"pid_integral"),
                (ColumnName.PidDerivativeColumn, u"pid_derivative")):
            model.setHorizontalHeaderItem(column, QtGui.QStandardItem(name))

        for column, paramName in (
                (ColumnName.OutputColumn, "output"),
                (ColumnName.SetpointColumn, "setpoint"),
                (ColumnName.PidGainColumn, "pid_gain"),
                (ColumnName.PidIntegralColumn, "pid_integral"),
                (ColumnName.PidDerivativeColumn, "pid_derivative")):
            model.registerParameter(column, paramName)

        model.setPollingOnColumn(ColumnName.OutputColumn)

        for column in (ColumnName.PidGainColumn,
                       ColumnName.PidIntegralColumn,
                       ColumnName.PidDerivativeColumn):
            self._instrTable.setColumnHidden(column, True)

        self.showProgramBoxAction.trigger()

if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    w = MeasureController()
    w.show()
    sys.exit(app.exec_())
    

