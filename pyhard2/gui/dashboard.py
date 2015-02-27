"""Launcher for the dashboard.

"""
import logging
logging.basicConfig()
from importlib import import_module  # DashboardConfig
from functools import partial
import yaml

import sip as _sip
for _type in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    _sip.setapi(_type, 2)
from PyQt4 import QtCore, QtGui, QtSvg
Qt = QtCore.Qt
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal
import PyQt4.Qwt5 as Qwt

from pyhard2.gui.controller import Controller
from pyhard2.gui.monitor import TimeSeriesData


class DoubleClickEventFilter(QtCore.QObject):

    """Emit doubleClicked signal on MouseButtonDblClick event."""

    doubleClicked = Signal()

    def __init__(self, parent):
        super(DoubleClickEventFilter, self).__init__(parent)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonDblClick:
            self.doubleClicked.emit()
            return True
        return False


class DashboardConfig(object):

    """Extend the config file format described in :func:`Config` to
    launch the `Dashboard` interface.

    The config files are extended with a `dashboard` section such as

    .. code-block:: yaml

        dashboard:
            name: Dashboard
            image: :/img/gaslines.svg
            labels:
                - name: LABEL1
                  pos: [0.25, 0.25]
                - name: LABEL2
                  pos: [0.5, 0.25]
                - name: LABEL3
                  pos: [0.75, 0.25]

    Where `Dashboard` is the name of the window. ``image:`` points to an
    svg file that will be displayed in the background of the window.
    ``labels:`` is a list of text labels containing the text `LABEL1`,
    `LABEL2`, and `LABEL3` displayed at the position given by ``pos:``
    as `(x,y)` pairs of relative coordinates.  `x` and `y` can be any
    value between 0 and 1.

    The other nodes also require the `pos` data in the format specified
    above, and optional ``scale`` and ``angle`` data may be passed as
    well.  Such as the previous file may become

    .. code-block:: yaml

        MODULE:
            COM1:
                - node: 1
                  name: first
                  pos: [0.25, 0.5]

                - node: 2
                  name: second
                  pos: [0.5, 0.5]
                  scale: 0.5
                  angle: 180

                - node: 3
                  name: third
                  pos: [0.75, 0.5]

    - `pos` gives the position as ``[x, y]`` pairs of relative
      coordinates (`x` and `y` are values between 0 and 1)  for the
      widget of the corresponding node.
    - `scale` scales the widget by the given amount.
    - `angle` rotates the widget by the given amount, in degree.

    Example:
        From the root directory of a working installation of `pyhard2`,
        the following line starts a dashboard containing virtual
        instruments::

            python pyhard2.ctrlr.__init__.py circat.yml -v

    """
    def __init__(self, filename):
        with open(filename, "rb") as file:
            self.yaml = yaml.load(file)
        self.windowTitle = "Dashboard"
        self.backgroundItem = QtGui.QGraphicsRectItem(0, 0, 640, 480)
        self.controllers = {}
        self.labels = {}

    def setupUi(self, dashboard):
        dashboard.setWindowTitle(self.windowTitle)
        dashboard.setBackgroundItem(self.backgroundItem)
        for text, (x, y) in self.labels.iteritems():
            textItem = dashboard.addSimpleText(text)
            textItem.setFlags(textItem.flags()
                              | QtGui.QGraphicsItem.ItemIgnoresTransformations)
            textItem.setPos(dashboard.mapToScene(QtCore.QPointF(x, y)))
        for controller, proxyWidgets in self.controllers.iteritems():
            dashboard.addControllerAndWidgets(controller, proxyWidgets)

    def parse(self):
        section = self.yaml.pop("dashboard")
        try:
            self.backgroundItem = QtSvg.QGraphicsSvgItem(section.pop("image"))
        except KeyError:
            pass
        self.windowTitle = section.pop("name", self.windowTitle)
        for name, pos in (dct.itervalues()
                          for dct in section.pop("labels", [])):
            self.labels[name] = pos

        for module, section in self.yaml.iteritems():
            try:
                controller = import_module("pyhard2.ctrlr.%s" % module)\
                    .createController()
            except:
                logger = logging.getLogger(__name__)
                logger.exception("%s controller failed to load." % module)
                continue
            self.controllers[controller] = []  # empty proxyWidget list
            for subsection in section.itervalues():
                for row, config in enumerate(subsection):
                    try:
                        x, y = config["pos"]
                    except KeyError:
                        continue
                    column = 0
                    proxyWidget = QtGui.QGraphicsProxyWidget()
                    proxyWidget.setWidget(controller.editorPrototype[column]
                                          .__class__())  # XXX
                    proxyWidget.setToolTip(config.get("name", row))
                    proxyWidget.setPos(x, y)
                    proxyWidget.rotate(config.get("angle", 0))
                    proxyWidget.setScale(config.get("scale", 1.5))
                    if isinstance(proxyWidget.widget(),
                                  QtGui.QAbstractSpinBox):
                        proxyWidget.setFlags(
                            proxyWidget.flags()
                            | proxyWidget.ItemIgnoresTransformations)
                    self.controllers[controller].append(proxyWidget)


class DashboardUi(QtGui.QMainWindow):

    """QMainWindow for the dashboard."""

    def __init__(self, parent=None):
        super(DashboardUi, self).__init__(parent)
        sp = QtGui.QSizePolicy
        centralWidget = QtGui.QWidget(self)
        self.setCentralWidget(centralWidget)
        self.centralLayout = QtGui.QHBoxLayout(centralWidget)
        self.tabWidget = QtGui.QTabWidget(self)
        self.centralLayout.addWidget(self.tabWidget)
        self.dashboardTab = QtGui.QWidget(self)
        self.tabWidget.addTab(self.dashboardTab, "Dashboard")
        self.dashboardTabLayout = QtGui.QHBoxLayout(self.dashboardTab)
        sizePolicy = QtGui.QSizePolicy(sp.Expanding, sp.Expanding)
        sizePolicy.setHorizontalStretch(3)
        self.graphicsView = QtGui.QGraphicsView(
            self,
            frameShape=QtGui.QFrame.NoFrame,
            frameShadow=QtGui.QFrame.Plain,
            sizePolicy=sizePolicy)
        self.graphicsScene = QtGui.QGraphicsScene(self)
        self.graphicsView.setScene(self.graphicsScene)
        self.plotArea = QtGui.QScrollArea(self)
        self.dashboardTabLayout.addWidget(self.graphicsView)
        self.dashboardTabLayout.addWidget(self.plotArea)
        self.plotAreaLayout = QtGui.QVBoxLayout(self.plotArea)

        self.menuWindow = QtGui.QMenu("Window")
        self.menuHelp = QtGui.QMenu("Help")
        self.menuBar().addMenu(self.menuWindow)
        self.menuBar().addMenu(self.menuHelp)

        self.aboutAction = QtGui.QAction(
            "About pyhard2", self,
            triggered=partial(Controller.aboutBox, self))
        self.menuHelp.addAction(self.aboutAction)

        self.tabWidget.currentChanged.connect(self.fitInView)

    @Slot()
    def fitInView(self):
        if self.tabWidget.currentIndex() is 0:
            self.graphicsView.fitInView(self.graphicsScene.sceneRect())

    def resizeEvent(self, event):
        super(DashboardUi, self).resizeEvent(event)
        self.fitInView()


class Dashboard(DashboardUi):

    """Implement the behavior of the GUI.

    Methods:
        windowTitle()
        setWindowTitle(title)
            This property holds the window title (caption).
        show: Show the widget and its child widgets.
        close: Close the widget.
    """

    def __init__(self, parent=None):
        super(Dashboard, self).__init__(parent)
        self.controllers = [self]
        self._monitors = []
        self._currentIndex = 0
        self.tabWidget.currentChanged.connect(self._tabChanged)

    def _addMonitorForSpinBox(self, item):
        def spinBox_valueChanged(value):
            plotCurve.data().append(value)
            plot.replot()

        plot = Qwt.QwtPlot(self.plotArea)
        plot.setTitle(item.toolTip())
        plot.setContextMenuPolicy(Qt.ActionsContextMenu)
        plot.setSizePolicy(QtGui.QSizePolicy.Preferred,
                           QtGui.QSizePolicy.Expanding)
        plot.hide()
        self._monitors.append(plot)
        self.plotArea.layout().addWidget(plot)
        plotCurve = Qwt.QwtPlotCurve()
        plotCurve.setData(TimeSeriesData())
        plotCurve.attach(plot)
        showMonitorAction = QtGui.QAction(u"monitor ...", item, checkable=True,
                                          toggled=plot.setVisible)
        plot.addAction(QtGui.QAction(u"hide", plot,
                                     triggered=showMonitorAction.toggle))
        plot.addAction(QtGui.QAction(u"clear", plot,
                                     triggered=plotCurve.data().clear))
        item.addAction(showMonitorAction)
        item.widget().valueChanged.connect(spinBox_valueChanged)

    def _connectSpinBoxToItem(self, spinBox, item, programmableColumn=None):
        def onItemChanged(item_):
            if item_ is item:
                spinBox.setValue(item.data())

        def onNewValueTriggered():
            item_ = item.model().item(item.row(), programmableColumn)
            value, ok = QtGui.QInputDialog.getDouble(
                self.graphicsView,  # parent
                spinBox.toolTip(),  # title
                text,               # label
                value=item_.data(),
                min=item_.minimum() if item_.minimum() is not None else 0.0,
                max=item_.maximum() if item_.maximum() is not None else 99.0,
                decimals=2,)
            if ok:
                item_.setData(value)

        if item.minimum():
            spinBox.setMinimum(item.minimum())
        if item.maximum():
            spinBox.setMaximum(item.maximum())
        spinBox.setReadOnly(item.isReadOnly())
        spinBox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons
                                 if item.isReadOnly() else
                                 QtGui.QAbstractSpinBox.UpDownArrows)
        item.model().itemChanged.connect(onItemChanged)

        if programmableColumn is not None:
            text = item.model().horizontalHeaderItem(programmableColumn).text()
            newValueAction = QtGui.QAction("new %s" % text.lower(), spinBox,
                                           triggered=onNewValueTriggered)
            spinBox.addAction(newValueAction)
            doubleClickEventFilter = DoubleClickEventFilter(spinBox.lineEdit())
            doubleClickEventFilter.doubleClicked.connect(
                newValueAction.trigger)
            spinBox.lineEdit().installEventFilter(doubleClickEventFilter)

    def _connectButtonToItem(self, button, item):
        def onItemChanged(item_):
            if item_ is item:
                button.setChecked(item.data())

        button.setEnabled(not item.isReadOnly())
        model = item.model()
        model.itemChanged.connect(onItemChanged)
        button.clicked.connect(item.setData)

    def _tabChanged(self, new):
        controller = self.controllers[self._currentIndex]
        if controller is not self:
            controller.timer.timeout.disconnect(controller.replot)
        controller = self.controllers[new]
        if controller is not self:
            controller.replot()
            controller.timer.timeout.connect(controller.replot)
        self._currentIndex = new

    def _goToController(self, controller, row=None):
        self.tabWidget.setCurrentIndex(
            self.tabWidget.indexOf(controller))
        if row is not None:
            controller.driverWidget.driverView.selectRow(row)

    def mapToScene(self, point):
        rect = self.graphicsScene.sceneRect()
        return QtCore.QPointF(rect.width() * point.x(),
                              rect.height() * point.y())

    def setBackgroundItem(self, backgroundItem):
        """Set the SVG image to use as a background."""
        backgroundItem.setParent(self.graphicsScene)
        backgroundItem.setFlags(QtSvg.QGraphicsSvgItem.ItemClipsToShape)
        backgroundItem.setZValue(-1)
        self.graphicsScene.addItem(backgroundItem)
        rect = backgroundItem.boundingRect()
        self.graphicsScene.setSceneRect(0, 0, rect.width(), rect.height())
        self.fitInView()

    def addSimpleText(self, text):
        """Add the `text` to the scene."""
        return self.graphicsScene.addSimpleText(text)

    def addSceneItem(self, item):
        """Add the `item` to the scene."""

        def onContextMenuRequested(pos):
            # cannot use ActionsContextMenu as the menu scales
            # with the widget
            view = self.graphicsView
            pos = view.viewport().mapToGlobal(
                view.mapFromScene(item.mapToScene(pos)))
            menu = QtGui.QMenu()
            menu.addActions(item.actions())
            menu.addActions(item.widget().actions())
            menu.exec_(pos)

        item.widget().setContextMenuPolicy(Qt.CustomContextMenu)
        item.widget().customContextMenuRequested.connect(
            onContextMenuRequested)
        item.setPos(self.mapToScene(item.pos()))
        self.graphicsScene.addItem(item)

    def addController(self, controller):
        """Add the `controller` as a new tab."""
        controller.timer.timeout.disconnect(controller.replot)
        self.menuWindow.addAction(QtGui.QAction(
            controller.windowTitle(), self.menuWindow,
            triggered=lambda checked: self._goToController(controller)))
        self.tabWidget.addTab(controller, controller.windowTitle())
        self.controllers.append(controller)

    def addControllerAndWidgets(self, controller, proxyWidgetList):
        """Add a `controller` and its associated widgets."""
        self.addController(controller)
        for row, proxyWidget in enumerate(proxyWidgetList):
            self.addSceneItem(proxyWidget)
            column = 0
            modelItem = controller.driverModel.item(row, column)
            if not modelItem:
                logging.getLogger(__name__).error(
                    "Size of configuration file and model do not match in %s" %
                    controller.windowTitle())
                continue
            proxyWidget.addAction(QtGui.QAction(
                u"go to controller...", proxyWidget,
                # needs early binding in the loop
                triggered=partial(self._goToController, controller, row)))
            widget = proxyWidget.widget()
            if isinstance(widget, QtGui.QAbstractSpinBox):
                self._addMonitorForSpinBox(proxyWidget)
                self._connectSpinBoxToItem(widget, modelItem,
                                           controller.programmableColumn())
            elif isinstance(widget, QtGui.QAbstractButton):
                self._connectButtonToItem(widget, modelItem)
            else:
                raise NotImplementedError

    def closeEvent(self, event):
        for controller in self.controllers:
            if controller is not self:
                controller.closeEvent(event)
        event.accept()


def main(argv):
    app = QtGui.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    w = Dashboard()
    w.show()
    config = DashboardConfig(argv[1])
    config.parse()
    config.setupUi(w)
    sys.exit(app.exec_())


if __name__ == "__main__":
    import sys
    main(sys.argv)
