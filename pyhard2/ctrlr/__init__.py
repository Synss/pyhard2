'''The :mod:`pyhard2.ctrlr` packages implement and lauch controllers.


The files in :mod:`pyhard2.ctrlr` initialize and launch the GUI
controllers.

In order to remain compatible with the
:class:`~pyhard2.gui.dashboard.Dashboard`, they must contain a function
named ``createController()`` that returns the initialized
:class:`~pyhard2.gui.controller.Controller`.

The initialization itself may be driven on the command line with the
help of the `ArgumentParser` setup in
:func:`~pyhard2.gui.controller.Config` or in the configuration file
passed to :func:`~pyhard2.gui.controller.Config`.

See also:
   The format for the configuration file and the command line arguments
   is describe in :func:`~pyhard2.gui.controller.Config`.

Example:
   The skeleton for the ``createController()`` function follows::

      from pyhard2.gui.controller import Config, Controller
      from pyhard2.driver import Serial
      from pyhard2.driver.MODULE import Driver  # import the actual driver
      import pyhard2.driver.virtual as virtual

      def createController():
         """Initialize controller."""
         config = Config("NAME")  # name of the driver module
         if config.virtual:
            driver = virtual.VirtualInstrument()
            # The virtual instrument comprises input, output, setpoint, and
            # a PID.
            iface = Controller.virtualInstrumentController(
               config, driver)
         else:
            driver = Driver(Serial(config.port))
            iface = Controller(config, driver)
            # We need at least one command.
            iface.addCommand(driver.SUBSYSTEM.COMMAND, "COLUMN_NAME")
         # We need at least one node.
         iface.addNode(0, "ROW_NAME")
         iface.populate()
         return iface

'''
