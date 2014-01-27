#beg_imports
import sys
import pyhard2.ctrlr as ctrlr
from tuthw1 import Fluke18x  # the instrument

from PyQt4 import QtGui
#end_imports


def start(serial_port):
    app = QtGui.QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    controller = ctrlr.MonitorController()
    controller.setWindowTitle(u"Logging multimeter")
    controller.addInstrumentClass(Fluke18x)
    opts = ctrlr.cmdline()
    opts.config = {serial_port: [dict(name="Fluke 18x",
                                      driver="Fluke18x")]}
    controller.loadConfig(opts)
    controller.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    start(sys.argv[1])

