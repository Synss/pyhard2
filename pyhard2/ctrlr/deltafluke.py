"""Graphical user interface for Delta-Elektronika--Fluke controller.


The Fluke 18x Series multimeter is used to read the temperature.  The
Delta-Elektronika SM 700 Series is a power supply and assumed to be connected to
port COM1.  Both instruments communicate via the software PID controller.

"""
import sys
from pyhard2.gui.controller import Config, Controller
import pyhard2.driver as drv
import pyhard2.driver.virtual as virtual
import pyhard2.driver.fluke as fluke
import pyhard2.driver.deltaelektronika as delta


class DeltaFluke(drv.Subsystem):

    """Instrument using a Fluke 18x as input (temperature) and the Delta
    SM 700 Series power supply as output.  Output is controller by a
    software PID.

    Use constant current (CC) mode.

    """
    def __init__(self, fluke_serial, delta_serial):
        super().__init__()
        self.fluke = fluke.Fluke18x(fluke_serial)
        self.delta = delta.Sm700Series(delta_serial)
        self.pid = virtual.PidSubsystem(
            self,
            vmin=0, vmax=self.delta.source.voltage.maximum,
            spmin=-100, spmax=2000)
        # Connections
        self.fluke.measure.signal.connect(self.pid.measure.write)
        self.fluke.measure.signal.connect(
            lambda value, node: self.pid.output.read(node))
        self.pid.output.signal.connect(self.delta.source.voltage.write)


def createController():
    """Initialize controller."""

    config = Config("deltaelektronika", "Delta-Fluke")
    if not config.nodes:
        config.nodes, config.names = ([1], ["DeltaFluke"])
    fluke_serial = drv.Serial(config.port)
    delta_serial = drv.Serial("COM1")
    driver = DeltaFluke(fluke_serial, delta_serial)
    iface = Controller(config, driver)
    iface.addCommand(driver.fluke.measure, "Temperature", poll=True)
    iface.addCommand(driver.pid.setpoint, "Setpoint", role="program")
    iface.addCommand(driver.delta.source.voltage, "Voltage", poll=True)
    iface.addCommand(driver.delta.source.current, "Current", poll=True)
    iface.addCommand(driver.pid.proportional, "PID P", hide=True, role="pidp")
    iface.addCommand(driver.pid.integral_time, "PID I", hide=True, role="pidi")
    iface.addCommand(driver.pid.derivative_time, "PID D", hide=True,
                     role="pidd")
    iface.populate()
    return iface


def main(argv):
    """Start controller."""
    from PyQt5 import QtWidgets
    app = QtWidgets.QApplication(argv)
    app.lastWindowClosed.connect(app.quit)
    iface = createController()
    iface.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)
