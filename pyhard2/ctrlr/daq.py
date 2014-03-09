# -*- coding: utf-8 -*-
"""
NI-DAQ and comedi controllers
=============================

Graphical user interface to NI-DAQ and comedi-compatible data acquisition
hardware.

"""

import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtCore, QtGui, QtSvg
Qt = QtCore.Qt
import pyhard2.rsc

import pyhard2.ctrlr as ctrlr
import pyhard2.driver as drv
Parameter, Action = drv.Parameter, drv.Action
import pyhard2.driver.daq as daq


class VirtualDio(object):

    def __init__(self):
        self.state = False


class VirtualDioInstrument(drv.Instrument):

    """Virtual instrument for DIO signal."""

    def __init__(self, socket, async=False):
        super(VirtualDioInstrument, self).__init__(socket, async)
        wrapper = drv.WrapperProtocol(VirtualDio(), async)
        self.main = drv.Subsystem(wrapper)
        self.main.add_parameter_by_name("state", "state")


class ValveButton(QtGui.QAbstractButton):

    """Button displaying the image of a valve."""

    def __init__(self, parent=None):
        super(ValveButton, self).__init__(parent)
        self.setCheckable(True)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self._rendererOn = QtSvg.QSvgRenderer(self)
        self._rendererOff = QtSvg.QSvgRenderer(self)
        self._rendererOn.load(":/img/valve_green.svg")
        self._rendererOff.load(":/img/valve_red.svg")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        if self.isChecked():
            self._rendererOn.render(painter)
        else:
            self._rendererOff.render(painter)

    def sizeHint(self):
        if self.isChecked():
            return self._rendererOn.defaultSize()
        else:
            return self._rendererOff.defaultSize()


class DaqModel(ctrlr.InstrumentModel):

    """Model handling non-serial configuration file."""

    def __init__(self, parent=None):
        super(DaqModel, self).__init__(parent)
        self.insertColumn(0)
        self.setHorizontalHeaderItem(ctrlr.ColumnName.MeasureColumn,
                                     QtGui.QStandardItem(u"state"))
        self.registerParameter(ctrlr.ColumnName.MeasureColumn, "state")

    def loadConfig(self, opts):
        for port in opts.config:
            thread = QtCore.QThread(self)
            for nrow, conf in enumerate(opts.config[port]):
                driverCls, mapper = self._instrumentClass[conf["driver"]]
                kw = dict(name=conf.get("name", "%i" % nrow),
                          lines="/".join((port, conf["extra"]["node"])))
                self.setVerticalHeaderItem(
                    nrow, QtGui.QStandardItem(kw["name"]))
                driver = driverCls(daq.DioSocket(**kw)
                                   if not opts.virtual else None)
                adapter = drv.DriverAdapter(driver, mapper)
                adapter.moveToThread(thread)
                for ncol in range(self.columnCount()):
                    item = self.itemFromIndex(self.index(nrow, ncol))
                    item.setInstrument(adapter)
                    item.connectHardware(role=Qt.CheckStateRole)
            thread.start()
            self._threads.append(thread)
        self.configLoaded.emit()


class DioController(ctrlr.MeasureController):

    """Controller with a `DaqModel` as default model."""

    def __init__(self, parent=None):
        super(DioController, self).__init__(parent)
        self.instrumentTable().setModel(DaqModel(self.instrumentTable()))

        editor = ctrlr.ButtonDelegate(ValveButton(), self._instrTable)
        self._instrTable.setItemDelegateForColumn(0, editor)
        editTriggers = QtGui.QAbstractItemView.SelectedClicked |\
                QtGui.QAbstractItemView.CurrentChanged
        self._instrTable.setEditTriggers(editTriggers)  # FIXME make accessor

    def createEditor(self, row, column=ctrlr.ColumnName.MeasureColumn):

        def onValueChanged(item):
            if (item.column() == column and
                item.row() == row):
                editor.setChecked(item.checkState())

        editor = ValveButton()
        editor.setContextMenuPolicy(Qt.ActionsContextMenu)
        model = self._instrTable.model()
        model.itemChanged.connect(onValueChanged)
        item = model.item(row, column)
        onValueChanged(item)  # set initial value
        editor.toggled.connect(item.setCheckState)

        return editor


def createController(opts):
    """
    Register `VirtualDioInstrument` and `ValveInstrument`.

    """
    iface = DioController()
    iface.setWindowTitle(u"DAQ controller")
    if not opts.config:
        opts.config = {"virtual": [dict(name="L%i" % idx,
                                        driver="virtual",
                                        extra={"node": "%i"})
                                   for idx in range(13)]}
    if opts.virtual:
        iface.setWindowTitle(iface.windowTitle() + u" [virtual]")
    iface.addInstrumentClass(VirtualDioInstrument, "virtual")
    iface.addInstrumentClass(daq.DioInstrument, "valve")
    iface.loadConfig(opts)
    return iface


def main(argv):
    """Start controller."""
    app = QtGui.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    opts = ctrlr.cmdline()
    if opts.config:
        try:
            opts.config = opts.config["daq"]
        except KeyError:
            pass
    iface = createController(opts)
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    import sys
    main(sys.argv)
