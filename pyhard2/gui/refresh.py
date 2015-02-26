import sip as _sip
for _type in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    _sip.setapi(_type, 2)

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal


class RefreshRateUi(QtGui.QWidget):

    def __init__(self, parent=None):
        super(RefreshRateUi, self).__init__(parent)
        self.refreshRateLayout = QtGui.QFormLayout(self)
        self.editor = QtGui.QDoubleSpinBox(
            self,
            minimum=0.01,
            maximum=3600.0,
            value=5.0)
        self.refreshRateLayout.addRow("Refresh /s", self.editor)


class RefreshRate(RefreshRateUi):

    def __init__(self, parent=None):
        super(RefreshRate, self).__init__(parent)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.editor.value() * 1000)
        self.editor.valueChanged.connect(
            lambda rate: self.timer.setInterval(rate * 1000))
