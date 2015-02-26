import matplotlib as mpl
from matplotlib.figure import Figure

from PyQt4.QtGui import QPalette
import PyQt4.QtCore as QtCore
mpl.use("Qt4Agg")
from matplotlib.backends.backend_qt4agg import (FigureCanvasQTAgg
                                                as FigureCanvas)


class MplWidget(FigureCanvas):

    def __init__(self, parent=None):
        fig = Figure()
        super(MplWidget, self).__init__(fig)
        self.setParent(parent)

    def setParent(self, parent):
        super(MplWidget, self).setParent(parent)
        if parent:
            color = parent.palette().brush(QPalette.Window).color()
            self.figure.set_facecolor("#%X%X%X" % (color.red(),
                                                   color.green(),
                                                   color.blue()))

    def sizeHint(self):
        return QtCore.QSize(320, 240)
