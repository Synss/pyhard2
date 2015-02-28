"""Extra widgets.

"""
from PyQt5 import QtWidgets, QtCore


class Counter(QtWidgets.QWidget):

    """Widget with a timer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.refreshRateLayout = QtWidgets.QFormLayout(self)
        self.editor = QtWidgets.QDoubleSpinBox(
            self,
            minimum=0.01,
            maximum=3600.0,
            value=5.0)
        self.refreshRateLayout.addRow("Refresh /s", self.editor)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.editor.value() * 1000)
        self.editor.valueChanged.connect(
            lambda rate: self.timer.setInterval(rate * 1000))


class ScientificSpinBox(QtWidgets.QDoubleSpinBox):

    """QDoubleSpinBox with a scientific display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(self.fontMetrics().width("0.000e-00"))
        self.setDecimals(50)

    def textFromValue(self, value):
        """Return the formatted value."""
        return "%.2e" % value

    def valueFromText(self, text):
        """Return the text as a float."""
        return float(text)
