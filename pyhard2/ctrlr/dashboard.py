"""
pyhard2.ctrlr.dashboard
=======================

Interface with several controllers.

"""

import sys
from functools import partial
from importlib import import_module

import sip
for cls in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    sip.setapi(cls, 2)

from PyQt4 import QtCore, QtGui, QtSvg
Qt = QtCore.Qt
Signal = QtCore.pyqtSignal

import PyQt4.Qwt5 as Qwt

from pyhard2.ctrlr import cmdline
from pyhard2.ctrlr.qt4.enums import ColumnName


class Dashboard(QtGui.QMainWindow):

    """
    Graphical user interface to interface with several controllers.

    Attributes
    ----------
    previewAllProgramsAction : QtGui.QAction
    startAllProgramsAction : QtGui.QAction
    stopAllProgramsAction : QtGui.QAction

    """
    def __init__(self, parent=None):
        super(Dashboard, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._ctrlrList = []
        self.__initUI()
        self.__initProgramPane()
        self.__initScene()
        self.__initStatusBar()
        self.__initMenuBar()

    def __initUI(self):
        widget = QtGui.QWidget(self)
        widget.setLayout(QtGui.QVBoxLayout(widget))
        self.setCentralWidget(widget)

    def __initScene(self):
        self._scene = QtGui.QGraphicsScene(self)
        self._view = QtGui.QGraphicsView(self._scene)
        self._view.setCacheMode(self._view.CacheBackground)
        self._view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._view.setFrameStyle(QtGui.QFrame.NoFrame | QtGui.QFrame.Plain)
        #self._view.setRenderHint(QtGui.QPainter.Antialiasing)
        #self._view.setRenderHint(QtGui.QPainter.TextAntialiasing)
        self.centralWidget().layout().addWidget(self._view)

    def __initStatusBar(self):
        statusBar = self.statusBar()
        #statusBar.showMessage(u"Initializing UI.")

    def __initMenuBar(self):
        menuBar = self.menuBar()
        self._windowMenu = QtGui.QMenu("Window")
        #self._controllerMenu = QtGui.QMenu("Controller")
        # submenu: -> {show|set port}

        self._helpMenu = QtGui.QMenu("Help")
        showAboutBoxAction = QtGui.QAction(self._helpMenu)
        showAboutBoxAction.setText("About...")
        self._helpMenu.addAction(showAboutBoxAction)

        menuBar.addMenu(self._windowMenu)
        menuBar.addMenu(self._helpMenu)

        self._windowMenu.addSeparator()

    def __initProgramPane(self):

        def previewAllPrograms(column=ColumnName.SetpointColumn):
            previewWindow = QtGui.QDialog()
            previewWindow.setWindowTitle("Start programs...")
            layout = QtGui.QVBoxLayout(previewWindow)

            for controller in self._ctrlrList:
                # filter out empty programs
                curves = (curve for curve in controller.previewCurves()
                          if curve.data().model().rowCount() and
                             curve.data().model().item(0, 0) is not None)
                for curve in curves:
                    monitor = Qwt.QwtPlot(curve.title(), previewWindow)
                    curve.attach(monitor)
                    layout.addWidget(monitor)

            if not layout.count():
                msg = QtGui.QMessageBox(QtGui.QMessageBox.Information,
                                        "Start programs...",
                                        "No program to start!")
                msg.setDetailedText(" ".join(
                    s.strip() for s in
                    """You can create programs in the controllers
                       accessible from the Window menu.""".splitlines()))
                msg.exec_()
                return False

            runBtn = QtGui.QPushButton(u"Run", previewWindow)
            runBtn.clicked.connect(partial(previewWindow.done, True))
            cancelBtn = QtGui.QPushButton(u"Cancel", previewWindow)
            cancelBtn.clicked.connect(partial(previewWindow.done, False))

            btnLayout = QtGui.QHBoxLayout()
            layout.addLayout(btnLayout)
            btnLayout.addWidget(runBtn)
            btnLayout.addWidget(cancelBtn)
            if previewWindow.exec_():
                startAllPrograms()

        def startAllPrograms():
            for controller in self._ctrlrList:
                controller.startAllProgramsAction.trigger()

        def stopAllPrograms():
            for controller in self._ctrlrList:
                controller.stopAllProgramsAction.trigger()

        self._programToolBar = QtGui.QToolBar(self)
        self.centralWidget().layout().addWidget(self._programToolBar)

        self.previewAllProgramsAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "document-print-preview",
                QtGui.QIcon(":/icons/Tango/document-print-preview.svg")),
            u"Preview all programs", self)
        self.previewAllProgramsAction.triggered.connect(previewAllPrograms)
        self._previewAllProgramsBtn = QtGui.QToolButton(self._programToolBar)
        self._previewAllProgramsBtn.setDefaultAction(
            self.previewAllProgramsAction)
        self._programToolBar.addWidget(self._previewAllProgramsBtn)

        self.startAllProgramsAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "media-seek-forward",
                QtGui.QIcon(":/icons/Tango/media-seek-forward.svg")),
            u"Start all programs", self)
        self.startAllProgramsAction.triggered.connect(startAllPrograms)
        self._startAllProgramsBtn = QtGui.QToolButton(self._programToolBar)
        self._startAllProgramsBtn.setDefaultAction(self.startAllProgramsAction)
        self._programToolBar.addWidget(self._startAllProgramsBtn)

        self.stopAllProgramsAction = QtGui.QAction(
            QtGui.QIcon.fromTheme(
                "process-stop",
                QtGui.QIcon(":/icons/Tango/process-stop.svg")),
            u"Stop all programs", self)
        self.stopAllProgramsAction.triggered.connect(stopAllPrograms)
        self._stopAllProgramsBtn = QtGui.QToolButton(self._programToolBar)
        self._stopAllProgramsBtn.setDefaultAction(self.stopAllProgramsAction)
        self._programToolBar.addWidget(self._stopAllProgramsBtn)

    def loadConfig(self, opts):
        """Load the configuration used to initialize the controllers."""
        dashboardCfg = opts.config.pop("dashboard")  # go virtual if no config
        self.setWindowTitle(dashboardCfg.get("name", ""))

        if "image" in dashboardCfg:
            backgroundItem = QtSvg.QGraphicsSvgItem(dashboardCfg["image"])
        else:
            backgroundItem = QtGui.QGraphicsRectItem(0, 0, 640, 480)
        backgroundItem.setFlags(backgroundItem.ItemClipsToShape)
        backgroundItem.setZValue(-1)
        self._scene.addItem(backgroundItem)

        rect = backgroundItem.boundingRect()
        width, height = rect.width(), rect.height()
        self._scene.setSceneRect(0, 0, width, height)
        self._view.fitInView(self._scene.sceneRect())

        for labelConfig in dashboardCfg.get("labels", []):
            pos = labelConfig.get("pos", "")
            if not pos: continue
            item = self._scene.addSimpleText(labelConfig.get("name", ""))
            item.setFlags(item.flags() | item.ItemIgnoresTransformations)
            item.setPos(width * pos[0], height * pos[1])

        for sectionName, section in opts.config.iteritems():
            childOpts = opts
            childOpts.config = section
            controller = import_module("pyhard2.ctrlr.%s" % sectionName)\
                    .createController(childOpts)
            self._addController(controller)
            for port in section:
                for nrow, conf in enumerate(section[port]):
                    if "pos" not in conf:
                        continue
                    editor = controller.createEditor(nrow)
                    editor.setToolTip(conf.get("name", ""))
                    # required for context menus:
                    editor.setWindowFlags(
                        editor.windowFlags() | Qt.BypassGraphicsProxyWidget)
                    item = self._scene.addWidget(editor)
                    item.rotate(conf.get("angle", 0))
                    item.setScale(conf.get("scale", 1.0))
                    if isinstance(editor, QtGui.QAbstractSpinBox):
                        item.setFlags(
                            item.flags() | item.ItemIgnoresTransformations)
                    item.setPos(width * conf["pos"][0],
                                height * conf["pos"][1])

    def _addController(self, controller):
        #controller.setWindowFlags(Qt.Popup)
        self.destroyed.connect(controller.close)
        self._ctrlrList.append(controller)
        action = QtGui.QAction(controller.windowTitle(), self._windowMenu)
        action.triggered.connect(controller.show)
        self._windowMenu.addAction(action)

    def resizeEvent(self, event):
        super(Dashboard, self).resizeEvent(event)
        self._view.fitInView(self._scene.sceneRect())


def main(argv):
    app = QtGui.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    iface = Dashboard()
    iface.loadConfig(cmdline())
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)

