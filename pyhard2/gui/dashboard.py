"""Launcher for the dashboard.

"""
import sip as _sip
for _type in "QDate QDateTime QString QTextStream QTime QUrl QVariant".split():
    _sip.setapi(_type, 2)
from PyQt4 import QtGui
import pyhard2.ctrlr as ctrlr


def main(argv):
    app = QtGui.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    w = ctrlr.Dashboard()
    w.show()
    config = ctrlr.DashboardConfig(argv[1])
    config.parse()
    config.setupUi(w)
    sys.exit(app.exec_())


if __name__ == "__main__":
    import sys
    main(sys.argv)
