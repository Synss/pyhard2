""" Controllers for pyhard2.ctrlr.qt4 """

from functools import partial

from PyQt4 import QtCore, QtGui
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal
Qt = QtCore.Qt

import PyQt4.Qwt5 as Qwt

from .widgets import Spreadsheet, Monitor, Curve, MeasureEdit
from .delegates import NumericDelegate
from .models import PollingInstrumentModel
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
            editor.setRange(self._minimum, self._maximum)
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
        def convert(item):
            if item is None:
                return 0.0
            else:
                try:
                    return float(item.text())
                except ValueError:
                    return 0.0

        return map(convert, (self.__model.item(i, column)
                             for column in (self.__xColumn, self.__yColumn)))

    def x(self, i):
        """Return `x` value."""
        return self.sample(i)[_ModelData.X]

    def y(self, i):
        """Return `y` value."""
        return self.sample(i)[_ModelData.Y]


class InstrumentTable(QtGui.QTableView):

    """
    TableView with a context menu.

    The context menu has two actions:
    - setting polling on or off on a column
    - setting logging on or off on a column.

    """
    def __init__(self, parent=None):
        super(InstrumentTable, self).__init__(parent)
        self.__setupUI()

    def __setupUI(self):
        horizontalHeader = self.horizontalHeader()
        horizontalHeader.setResizeMode(QtGui.QHeaderView.Stretch)
        horizontalHeader.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        verticalHeader = self.verticalHeader()
        verticalHeader.setResizeMode(QtGui.QHeaderView.ResizeToContents)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._showRightClickMenu)

    def _showRightClickMenu(self, pos):
        column = self.horizontalHeader().logicalIndexAt(pos)

        enablePollingAction = QtGui.QAction("Polling on column",
                                            self, checkable=True)
        enableLoggingAction = QtGui.QAction("Logging on column",
                                            self, checkable=True)
        enablePollingAction.setChecked(self.model().pollingOnColumn(column))
        enableLoggingAction.setChecked(self.model().loggingOnColumn(column))

        rightClickMenu = QtGui.QMenu(self)
        rightClickMenu.addAction(enablePollingAction)
        rightClickMenu.addAction(enableLoggingAction)

        action = rightClickMenu.exec_(self.mapToGlobal(pos))
        if action is None:
            return
        elif action == enablePollingAction:
            self.model().setPollingOnColumn(column, action.isChecked())
        elif action == enableLoggingAction:
            self.model().setLoggingOnColumn(column, action.isChecked())


class PidBox(QtGui.QGroupBox):

    """
    GroupBox with spin boxes for P, I, and D.

    .. image:: ../documentation/PidBox.png

    """
    def __init__(self, parent=None):
        super(PidBox, self).__init__(u"PID settings", parent)
        self.__setupUI()

    def __setupUI(self):
        self.pEditor = QtGui.QDoubleSpinBox(self)
        self.iEditor = QtGui.QDoubleSpinBox(self)
        self.dEditor = QtGui.QDoubleSpinBox(self)

        self.layout = QtGui.QFormLayout(self)
        self.layout.addRow(QtGui.QLabel(u"Proportional"), self.pEditor)
        self.layout.addRow(QtGui.QLabel(u"Integral"), self.iEditor)
        self.layout.addRow(QtGui.QLabel(u"Derivative"), self.dEditor)

        self.showAction = QtGui.QAction(u"Show PID", self)
        self.showAction.setCheckable(True)
        self.showAction.setChecked(True)
        self.showAction.triggered.connect(self.setVisible)


class ControlPanelElement(QtGui.QWidget):

    """ Widget representing panel elements. """

    def __init__(self, title, parent=None):
        super(ControlPanelElement, self).__init__(parent)
        self.title = title
        self.__setupUI()

    def __setupUI(self):
        self.showAction = QtGui.QAction(u"show %s" % self.title.lower(), self)
        self.showAction.setCheckable(True)
        self.showAction.setChecked(True)
        self.showAction.triggered.connect(self.setVisible)


class InstrumentPanel(ControlPanelElement):

    """
    Widget representing the instrument panel.

    .. image:: ../documentation/InstrumentPanel.png

    Attributes
    ----------
    refreshRateCtrl : QDoubleSpinBox
    table : InstrumentTable
    controlBox : QGroupBox
    pidBox : PidBox
    singleInstrumentAction : QAction
        Switch between `table` and `single instrument` views.

    """
    def __init__(self, parent=None):
        super(InstrumentPanel, self).__init__("instruments", parent)
        self.__setupUI()

    def __setupUI(self):
        self.refreshRateCtrl = QtGui.QDoubleSpinBox()
        self.refreshRateCtrl.setRange(0.1, 3600.0)
        self.refreshRateCtrl.setValue(10.0)

        formLayout = QtGui.QFormLayout()
        formLayout.addRow(QtGui.QLabel(u"Refresh /s"), self.refreshRateCtrl)

        self.table = InstrumentTable(self)
        self.table.setItemDelegate(_InstrumentItemDelegate(self.table))

        self.controlBox = QtGui.QGroupBox(u"Controls")
        self.controlBox.hide()
        self.controlBox.setLayout(QtGui.QFormLayout(self))

        self.pidBox = PidBox()

        self.layout = QtGui.QVBoxLayout(self)
        self.layout.addLayout(formLayout)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.controlBox)
        self.layout.addWidget(self.pidBox)

        self.singleInstrumentAction = QtGui.QAction(u"single instrument", self)
        self.singleInstrumentAction.setCheckable(True)
        self.singleInstrumentAction.setChecked(False)
        self.singleInstrumentAction.triggered.connect(
            self.controlBox.setVisible)
        self.singleInstrumentAction.triggered.connect(self.table.setHidden)

    def setupModel(self, model):
        """ Initialize GUI elements with the model. """
        self.table.setModel(model)

        model.setInterval(self.refreshRateCtrl.value() * 1000)
        self.refreshRateCtrl.valueChanged.connect(
            lambda dt: model.setInterval(1000 * dt))

        self.pidMapper = QtGui.QDataWidgetMapper(self)
        self.pidMapper.setSubmitPolicy(self.pidMapper.AutoSubmit)
        self.pidMapper.setItemDelegate(NumericDelegate(self.pidMapper))
        self.pidMapper.setModel(model)

        self.controlMapper = QtGui.QDataWidgetMapper(self.controlBox)
        self.controlMapper.setSubmitPolicy(QtGui.QDataWidgetMapper.AutoSubmit)
        self.controlMapper.setModel(model)

        self.table.selectionModel().currentRowChanged.connect(
            self.controlMapper.setCurrentModelIndex)
        self.table.selectionModel().currentRowChanged.connect(
            self.pidMapper.setCurrentModelIndex)

        for editor, column in (
                (self.pidBox.pEditor, ColumnName.PidGainColumn),
                (self.pidBox.iEditor, ColumnName.PidIntegralColumn),
                (self.pidBox.dEditor, ColumnName.PidDerivativeColumn)):
            self.pidMapper.addMapping(editor, column)

        model.configLoaded.connect(self.pidMapper.toFirst)
        model.configLoaded.connect(
            partial(self.setupControlBoxFromModel, model))

    def setupControlBoxFromModel(self, model):
        """
        Set up the instrument table according to the model currently loaded.

        """
        for column in range(model.columnCount()):
            if self.table.isColumnHidden(column): continue
            label = model.headerData(column, Qt.Horizontal)
            editor = QtGui.QDoubleSpinBox(self.controlBox)
            editor.setReadOnly(not model.item(0, column).isEditable())
            self.controlBox.layout().addRow(QtGui.QLabel(label), editor)
            self.controlMapper.addMapping(editor, column)

            item = model.item(0, column)
            try:
                editor.setMinimum(item.minimum())
            except TypeError:
                pass
            try:
                editor.setMaximum(item.maximum())
            except TypeError:
                pass

        model.configLoaded.connect(self.controlMapper.toFirst)


class MonitorPanel(ControlPanelElement):

    """
    Widget representing the monitor panel.

    .. image:: ../documentation/MonitorPanel.png

    Attributes
    ----------
    monitor : Monitor

    """
    def __init__(self, parent=None):
        super(MonitorPanel, self).__init__("monitor", parent)
        self.__loggingCurves = []  # prevent garbage collection
        self.__setupUI()

    def __setupUI(self):
        self.monitor = Monitor(self)

        self.layout = QtGui.QVBoxLayout(self)
        self.layout.addWidget(self.monitor)

    def setupModel(self, model):
        """ Initialize GUI elements with the model. """
        model.polling.connect(self.monitor.replot)
        model.configLoaded.connect(
            partial(self.setupLoggingCurvesFromModel, model))

    def setupLoggingCurvesFromModel(self, model):
        """ Initialize GUI elements with the model. """
        for row in range(model.rowCount()):
            vItem = model.verticalHeaderItem(row)
            for column in range(model.columnCount()):
                hItem = model.horizontalHeaderItem(column)
                text = "%s%%%s" % (vItem.text() if vItem else row,
                                   hItem.text() if hItem else column)
                loggingCurve = Curve(text)
                loggingCurve.setData(model.item(row, column).timeSeries())
                loggingCurve.attach(self.monitor)
                self.__loggingCurves.append(loggingCurve)


class ProgramPanel(ControlPanelElement):

    """
    Widget representing the programmable panel.

    .. image:: ../documentation/ProgramPanel.png

    Attributes
    ----------
    table : Spreadsheet
    preview : QwtPlot
    startAction : QAction
        Start the program.
    startAllAction : QAction
        Start all programs.
    stopAllAction : QAction
        Stop all programs.

    """
    def __init__(self, parent=None):
        super(ProgramPanel, self).__init__("program", parent)
        self.__previewCurves = []  # prevent garbage collection
        self.__setupUI()

    def __setupUI(self):
        self.table = Spreadsheet(self)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)
        self.table.horizontalHeader().setResizeMode(
            0, QtGui.QHeaderView.ResizeToContents)

        timeColumnDelegate = _NumericRangeDelegate(self.table)
        timeColumnDelegate.setRange(0.0, 7.0 * 24.0 * 3600.0)  # 7 days
        setpointColumnDelegate = NumericDelegate(self.table)

        self.table.setItemDelegateForColumn(0, timeColumnDelegate)
        self.table.setItemDelegateForColumn(1, setpointColumnDelegate)

        self.preview = Qwt.QwtPlot(self)

        self.startAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "media-playback-start",
                QtGui.QIcon(":/icons/Tango/media-playback-start.svg")),
            u"Start program", self)
        self.startAction.setCheckable(True)
        self.startAllAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "media-seek-forward",
                QtGui.QIcon(":/icons/Tango/media-seek-forward.svg")),
            u"Start all programs", self)
        self.stopAllAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "process-stop",
                QtGui.QIcon(":/icons/Tango/process-stop.svg")),
            u"Stop all programs", self)

        self.startBtn = QtGui.QToolButton(self)
        self.startAllBtn = QtGui.QToolButton(self)
        self.stopAllBtn = QtGui.QToolButton(self)

        self.startBtn.setDefaultAction(self.startAction)
        self.startAllBtn.setDefaultAction(self.startAllAction)
        self.stopAllBtn.setDefaultAction(self.stopAllAction)

        self.toolBar = QtGui.QToolBar(self)
        self.toolBar.addWidget(self.startBtn)
        self.toolBar.addWidget(self.startAllBtn)
        self.toolBar.addWidget(self.stopAllBtn)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.table.copyAction)
        self.toolBar.addAction(self.table.pasteAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.table.addRowAction)
        self.toolBar.addAction(self.table.removeRowAction)

        self.layout = QtGui.QVBoxLayout(self)
        self.layout.addWidget(self.toolBar, 2)
        self.layout.addWidget(self.table, 3)
        self.layout.addWidget(self.preview, 2)

    def setupModel(self, model):
        """ Initialize GUI elements with the model. """
        self.profileMapper = QtGui.QDataWidgetMapper(self)
        self.profileMapper.setSubmitPolicy(QtGui.QDataWidgetMapper.AutoSubmit)
        self.profileMapper.setItemDelegate(
            _ProgramTableDelegate(self.profileMapper))
        self.profileMapper.setModel(model)
        self.profileMapper.addMapping(self.table, ColumnName.SetpointColumn)

        self.startProgramMapper = QtGui.QDataWidgetMapper(self)
        self.startProgramMapper.setSubmitPolicy(
            QtGui.QDataWidgetMapper.AutoSubmit)
        self.startProgramMapper.setItemDelegate(_StartProgramDelegate(
            self.startProgramMapper))
        self.startProgramMapper.setModel(model)
        self.startProgramMapper.addMapping(
            self.startBtn, ColumnName.SetpointColumn)
        self.startAction.toggled.connect(self.startProgramMapper.submit)
        model.configLoaded.connect(self.startProgramMapper.toFirst)
        model.configLoaded.connect(
            partial(self.setupPreviewCurvesFromModel, model))

    def setupPreviewCurvesFromModel(self, model):
        """ Initialize GUI elements with the model. """
        def previewCurves(column=ColumnName.SetpointColumn):
            for row in range(model.rowCount()):
                item = model.item(row, column)
                profileModel = (item.profileModel() if item
                                else QtGui.QStandardItemModel(self))
                label = model.verticalHeaderItem(row).text()
                previewCurve = Curve(label)
                previewCurve.setData(_ModelData(profileModel))
                yield previewCurve

        def updatePreview(marker, curve):
            """Update program preview."""
            data = curve.data()
            x, y = (0.5 * (sample(data.size() - 2) + sample(data.size() - 1))
                    for sample in (data.x, data.y))
            marker.setValue(x, y)
            curve.plot().replot()

        for previewCurve in previewCurves():
            previewCurve.attach(self.preview)
            self.__previewCurves.append(previewCurve)

            marker = Qwt.QwtPlotMarker()
            marker.setLabel(previewCurve.title())
            marker.attach(self.preview)
            previewCurve.data().model().dataChanged.connect(
                partial(updatePreview, marker, previewCurve))


class Controller(QtGui.QMainWindow):

    """
    User interface to the controllers.

    .. image:: ../documentation/Controller.png

    """
    def __init__(self, parent=None):
        super(Controller, self).__init__(parent)
        self.__setupUI()
        self._setModel()

    def __repr__(self):
        return "%s(parent=%r)" % (self.__class__.__name__, self.parent())

    def __setupUI(self):
        self._instrPanel = InstrumentPanel(self)
        self._monitorPanel = MonitorPanel(self)
        self._programPanel = ProgramPanel(self)
        self._programPanel.startAllAction.triggered.connect(
            self._startAllPrograms)
        self._programPanel.stopAllAction.triggered.connect(
            self._stopAllPrograms)

        self._programPanel.setSizePolicy(QtGui.QSizePolicy.Fixed,
                                        QtGui.QSizePolicy.Expanding)

        self._viewMenu = QtGui.QMenu(u"View", self.menuBar())
        self._viewMenu.addAction(self._programPanel.showAction)
        self._viewMenu.addAction(self._monitorPanel.showAction)
        self._viewMenu.addAction(self._instrPanel.pidBox.showAction)
        self._viewMenu.addAction(self._instrPanel.singleInstrumentAction)
        self.menuBar().addMenu(self._viewMenu)

        centralWidget = QtGui.QWidget()
        layout = QtGui.QHBoxLayout(centralWidget)
        layout.addWidget(self._instrPanel)
        layout.addWidget(self._monitorPanel)
        layout.addWidget(self._programPanel)
        self.setCentralWidget(centralWidget)

    def _setModel(self, model=None):
        if model is None:
            model = PollingInstrumentModel(self)

        self._instrPanel.setupModel(model)
        self._monitorPanel.setupModel(model)
        self._programPanel.setupModel(model)

        self._instrPanel.table.selectionModel().currentRowChanged.connect(
            self._programPanel.profileMapper.setCurrentModelIndex)
        self._instrPanel.table.selectionModel().currentRowChanged.connect(
            self._programPanel.startProgramMapper.setCurrentModelIndex)

    def _startAllPrograms(self, checked, column=ColumnName.SetpointColumn):
        """Start every program stored in this controller."""
        model = self._instrPanel.table.model()
        for nRow in range(model.rowCount()):
            spItem = model.item(nRow, column)
            if spItem:
                spItem.startRamp()

    def _stopAllPrograms(self, checked, column=ColumnName.SetpointColumn):
        """Stop every running program stored in this controller."""
        model = self._instrPanel.table.model()
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
        return self._instrPanel.table

    def createEditor(self, row, column=ColumnName.MeasureColumn):
        """
        Return editor for an item of the `instrumentTable` at `row` and
        `column`.
        
        """
        def updateEditor(item):
            if (item.column() == column and item.row() == row):
                editor.setValue(item.data(role=Qt.DisplayRole))

        model = self._instrPanel.table.model()
        editor = MeasureEdit()
        item = model.item(row, column)
        minimum, maximum = item.minimum(), item.maximum()
        if minimum is not None:
            editor.setMinimum(minimum)
        if maximum is not None:
            editor.setMaximum(maximum)
        editor.setCurveData(item.timeSeries())
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
        self._instrPanel.table.model().addInstrumentClass(instrCls, name, mapper)

    def loadConfig(self, opts):
        """Load config file into the controller."""
        self._instrPanel.table.model().loadConfig(opts)


class MeasureController(Controller):
    """
    Controller with a single table.

    The instrument table contains a single column registered to the
    parameter `measure`.

    .. image::  ../documentation/MeasureController.png

    """
    def __init__(self, parent=None):
        super(MeasureController, self).__init__(parent)

        model = self.instrumentTable().model()
        model.insertColumn(0)
        model.setHorizontalHeaderItem(ColumnName.MeasureColumn,
                                      QtGui.QStandardItem(u"measure"))
        model.registerParameter(ColumnName.MeasureColumn, "measure")
        model.setPollingOnColumn(ColumnName.MeasureColumn)        
        model.setLoggingOnColumn(ColumnName.MeasureColumn)

        self._instrPanel.pidBox.showAction.trigger()
        self._monitorPanel.showAction.trigger()
        self._programPanel.showAction.trigger()


class MonitorController(MeasureController):
    """
    Controller with measure reading and a monitor.

    The instrument table contains a single column registered to the
    parameter `measure`.

    .. image:: ../documentation/MonitorController.png

    """
    def __init__(self, parent=None):
        super(MonitorController, self).__init__(parent)

        self._monitorPanel.showAction.trigger()


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
        model.setLoggingOnColumn(ColumnName.SetpointColumn)
        model.setLoggingOnColumn(ColumnName.OutputColumn)

        for column in (ColumnName.PidGainColumn,
                       ColumnName.PidIntegralColumn,
                       ColumnName.PidDerivativeColumn):
            self._instrPanel.table.setColumnHidden(column, True)

        self._programPanel.showAction.trigger()

if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    w = MeasureController()
    w.show()
    sys.exit(app.exec_())
    

