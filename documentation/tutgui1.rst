.. module:: pyhard2.ctrlr.qt4


GUI Tutorial 1: Initialization of the GUI from Python
=====================================================


The code from this tutorial is available for download at
:download:`tutgui1.py`.


For the logging application (see :doc:`tuthw1` and :doc:`tuthw2`), a
`MonitorController` is the most appropriate (see :doc:`tutgui0`).  Creating
the GUI is then relatively simple:

.. literalinclude:: tutgui1.py
   :start-after: #beg_imports
   :end-before: #end_imports

.. warning::

   QtGui must be imported **after** the `pyhard2.ctrlr` classes because
   pyhard2 uses PyQt4's API version 2.

.. literalinclude:: tutgui1.py
   :pyobject: start
   :emphasize-lines: 4,7-10

>>> serial_port = "COM1"
>>> start(serial_port)

:meth:`~Controller.addInstrumentClass` registers drivers with the GUI and
:meth:`~Controller.loadConfig` performs the actual initialization.  `cmdline`
may be used to parse arguments passed to the program and returns default values
here.  The `config` attributes maps a list of instruments to a serial port.
The value of the `driver` key must be the name of the registered drivers.  Also
note that the name of the driver can be set to another value with the `name`
keyword argument to `addInstrumentClass()`


.. note::

   Registering classes before loading the configuration file has the advantage
   that a single GUI can be used with different drivers.


A simpler way to write the argument to `loadConfig` is as a YAML formula,
provided `pyyaml <http://pyyaml.org>`_ is installed, a configuration file can
be written in a file named, e.g., `fluke.yml`::

   COM1:
      - name: Fluke 18x
        driver: Fluke18x

and the `loadConfig` call becomes::

   with open("fluke.yml", "r") as config:
      controller.loadSerialConfig(config)

.. note::

   In order to allow writing a single configuration file for several
   instruments handling several instruments, the configuration may
   further be mapped to the module name::
      
      fluke:
          COM1:
              - name: Fluke 18x
                driver: Fluke18x

   is thus equivalent to the other YAML formula given.

.. note::

   Extra arguments necessary to initialize the `instrument` are added in a
   dictionary at the `extra` key as in::

      bronkhorst:
         COM2:
            - name: CO MFC
              driver: MFC
              extra: {node: 3}


pyhard2 conventions for modules in :mod:`pyhard2.ctrlr`
-------------------------------------------------------


Whereas the previous example is suitable within a live session, it is
recommended to follow a set of simple conventions when writing the module:

- The interface of the controller is returned by a :func:`createController`
  function.
- This function takes one argument, `opts`, the options passed at the command
  line.
- Command line arguments are parsed in the :func:`main` function by calling
  the function :func:`pyhard2.ctrlr.cmdline`.
- The :class:`QApplication` is instantiated in :func:`main`.

The command line arguments are the path to the YAML configuration file and an
optional `-v` or `--virtual` switch that can be used to load a
:class:`~pyhard2.driver.virtual.VirtualInstrument` instead of the actual driver
in order to test the GUI offline.


Whereas this example demonstrates the simplest case where the GUI handles the
driver mostly automatically, :doc:`tutgui2` shows the general case.
:doc:`tutgui3` shows how to make a dashboard organizing several controllers.


.. seealso::

   Class :class:`pyhard2.ctrlr.qt4.controllers.MeasureController`
      API documentation of the `Controller` class.

   Class :class:`pyhard2.ctrlr.qt4.controllers.MonitorController`
      API documentation of the MonitorController class.

   Class :class:`pyhard2.ctrlr.qt4.controllers.SetpointController`
      API documentation of the MonitorSetpointController class.

   Module :mod:`pyhard2.ctrlr.fluke`
      API documentation of the Fluke controller module.

   Function :func:`pyhard2.ctrlr.cmdline`
      API documentation of the `cmdline` function.

   Class :class:`pyhard2.driver.virtual.VirtualInstrument`
      API documentation of the `VirtualInstrument` class.

   `yaml.org <http://yaml.org/spec/1.2/spec.html>`_
      YAML specifications.

   `pyyaml.org <http://pyyaml.org>`_ 
      Python bindings for YAML.
