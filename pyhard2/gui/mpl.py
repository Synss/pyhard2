"""Matplotlib helpers.

"""
import matplotlib as mpl

from matplotlib.figure import Figure
import matplotlib.lines as lines
import matplotlib.transforms as mtransforms
import matplotlib.text as mtext

from PyQt5 import QtCore
from PyQt5.QtGui import QPalette
mpl.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg
                                                as FigureCanvas)


class MplWidget(FigureCanvas):

    """Matplotlib Qt widget."""

    def __init__(self, parent=None):
        fig = Figure()
        super(MplWidget, self).__init__(fig)
        self.setParent(parent)

    def setParent(self, parent):
        """Set the colors to the parent's theme."""
        super(MplWidget, self).setParent(parent)
        if parent:
            color = parent.palette().brush(QPalette.Window).color()
            self.figure.set_facecolor("#%X%X%X" % (color.red(),
                                                   color.green(),
                                                   color.blue()))

    def sizeHint(self):
        return QtCore.QSize(320, 240)


class Line(lines.Line2D):

    """Line with text, from
       http://matplotlib.org/examples/api/line_with_text.html

    """
    def __init__(self, *args, **kwargs):
        # we'll update the position when the line data is set
        self.text = mtext.Text(0, 0, '')
        lines.Line2D.__init__(self, *args, **kwargs)

        # we can't access the label attr until *after* the line is
        # inited
        self.text.set_text(self.get_label())

    def set_figure(self, figure):
        self.text.set_figure(figure)
        lines.Line2D.set_figure(self, figure)

    def set_axes(self, axes):
        self.text.set_axes(axes)
        lines.Line2D.set_axes(self, axes)

    def set_transform(self, transform):
        # 2 pixel offset
        texttrans = transform + mtransforms.Affine2D().translate(2, 2)
        self.text.set_transform(texttrans)
        lines.Line2D.set_transform(self, transform)

    def set_data(self, x, y):
        if len(x):
            self.text.set_position((x[-1], y[-1]))

        lines.Line2D.set_data(self, x, y)

    def draw(self, renderer):
        # draw my label at the end of the line with 2 pixel offset
        lines.Line2D.draw(self, renderer)
        self.text.draw(renderer)
