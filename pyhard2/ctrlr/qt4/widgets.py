""" Widgets for pyhard2.ctrlr.qt4 """

import csv as _csv
import StringIO as _StringIO

from PyQt4 import QtCore, QtGui
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal
Qt = QtCore.Qt
import PyQt4.Qwt5 as Qwt


class _DoubleClickEvent(QtCore.QObject):
    """ Filter `MouseButtonDblClick` and emit a `doubleClicked` signal. """

    doubleClicked = Signal()

    def __init__(self, parent):
        super(_DoubleClickEvent, self).__init__(parent)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonDblClick:
            self.doubleClicked.emit()
            return True
        return False


class Curve(Qwt.QwtPlotCurve):

    """ Curve deriving from :class:`Qwt.QwtPlotCurve`. """

    def __init__(self, title=""):
        super(Curve, self).__init__(title)

    def setEmphasis(self, emphasis=True):
        """Increase width of `Curve`."""
        if emphasis:
            pen = QtGui.QPen(self.pen())
            pen.setWidth(2)
            self.setPen(pen)
        else:
            self.setPen(QtGui.QPen())


class Monitor(Qwt.QwtPlot):

    """ Monitor deriving from :class:`Qwt.QwtPlot`. """

    def __init__(self, parent=None):
        super(Monitor, self).__init__(parent)
        self.setAxisTitle(Qwt.QwtPlot.xBottom, "time / s")
        self.__initZoomer()
        self.__initContextMenu()

    def __initZoomer(self):
        def on_zoomer_zoomed(rect):
            if self._zoomer.zoomRectIndex() == 0:
                self._clearZoomStack()

        self._zoomer = Qwt.QwtPlotZoomer(Qwt.QwtPlot.xBottom,
                                         Qwt.QwtPlot.yLeft,
                                         Qwt.QwtPicker.DragSelection,
                                         Qwt.QwtPicker.AlwaysOff,
                                         self.canvas())
        self._zoomer.setRubberBandPen(QtGui.QPen(QtGui.QColor("white")))
        self._zoomer.zoomed.connect(on_zoomer_zoomed)
        # ZOOM IN: left and drag; ZOOM OUT: shift + left
        self._zoomer.setMousePattern(Qwt.QwtEventPattern.MouseSelect2,
                                     Qt.LeftButton, Qt.ShiftModifier)
        self._zoomer.setTrackerPen(QtGui.QPen(QtGui.QColor("white")))

    def __initContextMenu(self):
        self.setContextMenuPolicy(Qt.ActionsContextMenu)

        self.zoomOutAction = QtGui.QAction("Zoom out", self)
        self.zoomOutAction.triggered.connect(self._clearZoomStack)
        self.addAction(self.zoomOutAction)

        self.exportAction = QtGui.QAction("Export as text", self)
        self.exportAction.triggered.connect(self.export)
        self.addAction(self.exportAction)

    def export(self):
        """ Export the content of the monitor to a file. """
        try:
            with open(QtGui.QFileDialog.getSaveFileName(self), "w") as csvfile:
                csvwriter = _csv.writer(csvfile, delimiter="\t")
                for curve in self.itemList():
                    csvfile.write("%s\n" % curve.title().text())
                    csvwriter.writerows(curve.data())
        except IOError:
            pass  # User canceled QFileDialog

    def _clearZoomStack(self):
        """Force autoscaling and clear the zoom stack."""
        self.setAxisAutoScale(Qwt.QwtPlot.yLeft)
        self.setAxisAutoScale(Qwt.QwtPlot.yRight)
        self.setAxisAutoScale(Qwt.QwtPlot.xBottom)
        self.setAxisAutoScale(Qwt.QwtPlot.xTop)
        self.replot()
        self._zoomer.setZoomBase()


class ScientificSpinBox(QtGui.QDoubleSpinBox):

    """ QDoubleSpinBox with a scientific display. """

    def __init__(self, parent=None):
        super(ScientificSpinBox, self).__init__(parent)
        self.setMinimumWidth(self.fontMetrics().width("0.000e-00"))

    def textFromValue(self, value):
        return "%.2e" % value

    def valueFromText(self, text):
        return float(text)


class MeasureEdit(ScientificSpinBox):

    """
    ScientificSpinBox with monitoring (in a pop-up) and the possibility
    to set a `setpoint` value.

    """
    setpointValue = Signal(float)

    def __init__(self, parent=None):
        super(MeasureEdit, self).__init__(parent)
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.__initMonitor()
        self.__initActions()

    def __initMonitor(self):
        self._monitor = Monitor()
        self._curve = Curve()
        self._curve.attach(self._monitor)

    def __initActions(self):

        def onNewSetpointAction():
            value, ok = QtGui.QInputDialog.getDouble(
                self,            # parent
                self.toolTip(),  # title
                "setpoint:",     # label
                decimals=2       # decimals
            )
            if ok:
                self.setpointValue.emit(value)

        self._showTraceAction = QtGui.QAction("show trace...", self)
        self._showTraceAction.setCheckable(True)
        self._showTraceAction.triggered.connect(self._monitor.setVisible)
        self.addAction(self._showTraceAction)

        dblClickFilter = _DoubleClickEvent(self.lineEdit())
        dblClickFilter.doubleClicked.connect(onNewSetpointAction)
        self.lineEdit().installEventFilter(dblClickFilter)

        self._setpointAction = QtGui.QAction("new setpoint", self)
        self._setpointAction.triggered.connect(onNewSetpointAction)

    def enableSetpointAction(self, enable):
        if enable:
            self.addAction(self._setpointAction)    
        else:
            self.removeAction(self._setpointAction)

    def monitor(self):
        """ Returns the monitor. """
        return self._monitor

    def setCurveData(self, curveData):
        """ Sets data. """
        self._curve.setData(curveData)

    def setReadOnly(self, readOnly):
        if readOnly:
            self.setButtonSymbols(self.NoButtons)
        else:
            self.setButtonSymbols(self.UpDownArrows)
        super(MeasureEdit, self).setReadOnly(readOnly)


class Spreadsheet(QtGui.QTableView):
    """
    A simple spreadsheet implementing copy/paste.

    Attributes
    ----------
    copyAction, pasteAction : QtGui.QAction
    addRow, removeRow : QtGui.QAction

    """
    def __init__(self, parent=None):
        super(Spreadsheet, self).__init__(parent)
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.setSelectionMode(self.ContiguousSelection)
        self.__initActions()

    def __initActions(self):
        self.copyAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "edit-copy",
                QtGui.QIcon(":/icons/Tango/edit-copy.svg")),
            u"Copy", self)
        self.copyAction.setShortcut(QtGui.QKeySequence.Copy)
        self.copyAction.triggered.connect(self._copy)
        self.addAction(self.copyAction)

        self.pasteAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "edit-paste",
                QtGui.QIcon(":/icons/Tango/edit-paste.svg")),
            u"Paste", self)
        self.pasteAction.setShortcut(QtGui.QKeySequence.Paste)
        self.pasteAction.triggered.connect(self._paste)
        self.addAction(self.pasteAction)

        self.addRowAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "list-add",
                QtGui.QIcon(":/icons/Tango/list-add.svg")),
            u"Add row", self)
        self.addRowAction.triggered.connect(self._addRow)
        self.addAction(self.addRowAction)

        self.removeRowAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "list-remove",
                QtGui.QIcon(":/icons/Tango/list-remove.svg")),
            u"Remove row", self)
        self.removeRowAction.triggered.connect(self._removeSelectedRows)
        self.addAction(self.removeRowAction)

    def _copy(self):
        """ Copy selected cells as csv. """
        previous = QtCore.QModelIndex()
        fields = []
        for idx in sorted(self.selectedIndexes()):
            if idx.row() == previous.row():
                fields[-1].append(idx.data())
            else:
                fields.append([idx.data()])
            previous = idx
        csvfile = _StringIO.StringIO()
        writer = _csv.writer(csvfile)
        writer.writerows(fields)
        QtGui.QApplication.clipboard().setText(csvfile.getvalue())

    def _paste(self):
        """ Paste csv buffer. """
        csvfile = _StringIO.StringIO(QtGui.QApplication.clipboard().text())
        dialect = _csv.Sniffer().sniff(csvfile.read(1024))
        csvfile.seek(0)
        reader = _csv.reader(csvfile, dialect)
        model = self.model()
        idx = self.currentIndex()
        for nRow, line in enumerate(reader):
            row = idx.row() + nRow
            if row >= model.rowCount():
                model.setRowCount(row + 1)
            for nCol, data in enumerate(line):
                if not data: continue
                col = idx.column() + nCol
                item = model.itemFromIndex(model.index(row, col))
                try:
                    item.setData(data, role=Qt.DisplayRole)
                except AttributeError:
                    QtGui.QMessageBox.critical(
                        self,  # parent
                        self.__class__.__name__ ,  # title
                        " ".join(("Invalid clipboard data,",
                                  "incorrect number of columns.")))
                    return

    def _addRow(self):
        """ Add one row after the row. """
        current = self.currentIndex()
        if not current.isValid():
            return
        model = self.model()
        model.insertRow(current.row() + 1,
                        [model.itemPrototype()
                         for __ in range(model.columnCount())])

    def _removeSelectedRows(self):
        """ Remove selected rows or current row if no selection. """
        selection = [idx for idx in self.selectionModel().selectedRows()]
        if not selection:
            selection = [self.currentIndex()]
        model = self.model()
        for row in reversed(sorted(idx.row() for idx in selection)):
            model.removeRow(row)
        # add empty rows in the end
        for row in range(len(selection)):
            model.insertRow(model.rowCount(),
                            [model.itemPrototype()
                             for __ in range(model.columnCount())])

