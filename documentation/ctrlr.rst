GUI controllers
===============

The files in `pyhard2.ctrlr` initialize and launch the GUI controllers.

In order to remain compatible with the :class:`~pyhard2.ctrlr.Dashboard`,
they must contain a function named ``createController()`` that returns
the initialized :class:`~pyhard2.ctrlr.Controller`.

The initialization itself may be driven on the command line with the
help of the `ArgumentParser` setup in :func:`~pyhard2.ctrlr.Config` or
in the configuration file passed to :func:`~pyhard2.ctrlr.Config`.

See also:
   The format for the configuration file and the command line arguments
   is describe in :func:`~pyhard2.ctrlr.Config`.

Example:
   The skeleton for the ``createController()`` function follows::

      import pyhard2.ctrlr as ctrlr
      import pyhard2.driver as drv
      from pyhard2.driver.MODULE import Driver  # import the actual driver
      import pyhard2.driver.virtual as virtual

      def createController():
         """Initialize controller."""
         args = ctrlr.Config("NAME")  # name of the driver module
         if args.virtual:
            driver = virtual.VirtualInstrument()
            # The virtual instrument comprises input, output, setpoint, and
            # a PID.
            iface = ctrlr.Controller.virtualInstrumentController(
               driver, u"NAME")  # title of the controller window
         else:
            driver = Driver(drv.Serial(args.port))
            iface = ctrlr.Controller(driver, u"NAME")
            # We need at least one command.
            iface.addCommand(driver.SUBSYSTEM.COMMAND, "COLUMN_NAME")
         # We need at least one node.
         iface.addNode(0, "ROW_NAME")
         iface.populate()
         return iface


DAQ
---
.. automodule:: pyhard2.ctrlr.daq

Bronkhorst
----------
.. automodule:: pyhard2.ctrlr.bronkhorst

Fluke
-----
.. automodule:: pyhard2.ctrlr.fluke

Pfeiffer
--------
.. automodule:: pyhard2.ctrlr.pfeiffer

Watlow
------
.. automodule:: pyhard2.ctrlr.watlow

