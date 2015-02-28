"""Bare minimum for a Watlow Series 982 driver."""

import unittest
import pyhard2.driver as drv
# We define shortcuts.
Cmd, Access = drv.Command, drv.Access

import pyhard2.ctrlr as ctrlr
import pyhard2.driver.virtual as virtual


class XonXoffProtocol(drv.CommunicationProtocol):

    """Communication using the XON/XOFF protocol."""

    def _xonxoff(self):
        xonxoff = self._socket.read(2)
        if not xonxoff == "\x13\x11":
            raise drv.DriverError("Expected XON/XOFF (%r) got %r instead."
                                  % ("\x13\x11", xonxoff))

    def read(self, context):
        line = "? {mnemonic}\r".format(mnemonic=context.reader)
        self._socket.write(line)
        self._xonxoff()
        return float(self._socket.readline())  # convert unicode to float

    def write(self, context):
        line = "= {mnemonic} {value}\r".format(mnemonic=context.writer,
                                               value=context.value)
        self._socket.write(line)
        self._xonxoff()


class Series982(drv.Subsystem):

    """Driver to Watlow Series 982 controller."""

    def __init__(self, socket, parent=None):
        super(Series982, self).__init__(parent)
        self.setProtocol(XonXoffProtocol(socket))
        self.temperature1 = Cmd("C1", access=Access.RO)
        self.temperature2 = Cmd("C2", access=Access.RO)
        self.setpoint = Cmd("SP1", minimum=-250, maximum=9999)  # assume deg C
        self.power = Cmd("PWR", access=Access.RO, minimum=0, maximum=100)
        self.operation = drv.Subsystem(self)
        self.operation.pid = drv.Subsystem(self.operation)
        self.operation.pid.proportional = Cmd("PB1")
        self.operation.pid.integral = Cmd("IT1", minimum=0.00, maximum=99.99)
        self.operation.pid.derivative = Cmd("DE1", minimum=0.00, maximum=9.99)


def createController():
    # Parse the commandline arguments:
    args = ctrlr.Config("watlow")
    # Create an driver instance:
    driver = Series982(drv.Serial(args.port))
    # Create an interface instance:
    iface = ctrlr.Controller(driver, u"Watlow")
    # Add commands, create new columns in the `driver table`:
    iface.addCommand(driver.temperature1, "TC sample", poll=True, log=True)
    iface.addCommand(driver.temperature2, "TC heater", poll=True, log=True)
    iface.addCommand(driver.setpoint, "setpoint", log=True, role="program")
    iface.addCommand(driver.power, "output", poll=True, log=True)
    iface.addCommand(driver.operation.pid.a1.gain, "PID P", hide=True,
                     role="pidp")
    iface.addCommand(driver.operation.pid.a1.integral, "PID I", hide=True,
                     role="pidi")
    iface.addCommand(driver.operation.pid.a1.derivative, "PID D", hide=True,
                     role="pidd")
    # Add at least one node:
    iface.addNode(0, u"Watlow")
    # Fill the table with a call to `populate`
    iface.populate()
    return iface


class TestSeries982(unittest.TestCase):

    def setUp(self):
        socket = drv.TesterSocket()
        # socket.msg = {} such as: dict(send message: receive message)
        socket.msg = {"? PB1\r": "\x13\x1111\r",  # send lhs, receive rhs
                      "= DE1 3\r": "\x13\x11",
                      "? C1\r": "\x13\x1150\r",
                      "= SP1 25\r": "\x13\x11"}
        self.i = Series982(socket)

    def test_read(self):
        self.assertEqual(self.i.temperature1.read(), 50)

    def test_write(self):
        self.i.setpoint.write(25)

    def test_read_operation_pid(self):
        self.assertEqual(self.i.operation.pid.proportional.read(), 11)

    def test_write_operation_pid(self):
        self.i.operation.pid.derivative.write(3)


def main():
    import sys
    import PyQt4.QtGui as QtGui
    app = QtGui.QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    iface = createController()
    iface.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

