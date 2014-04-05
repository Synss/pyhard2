.. module:: pyhard2.ctrlr.qt4


=================
GUI API Tutorials
=================


0. Graphical user interfaces
============================

The graphical user interfaces in pyhard2 are built on PyQt4.  The module
:mod:`pyhard2.ctrlr.qt4` provides generic controllers with different features.


The :class:`Controller` controller is the simplest and displays a simple
table as shown

.. image:: Controller.png
   :alt: screenshot of :class:`pyhard2.ctrlr.Controller`


The :class:`MonitorController` adds a monitor to the `Controller`
controller.

.. image:: MonitorController.png
   :alt: screenshot of :class:`pyhard2.ctrlr.MonitorController`


The :class:`MonitorSetpointController` controller also contains a PID
controller and a table to ramp the setpoint.

.. image:: MonitorSetpointController.png
   :alt: screenshot of :class:`pyhard2.ctrlr.MonitorSetpointController` 
   :scale: 85%


.. note::

   The table is really where the communication with the hardware happens.  The
   most common configuration has one hardware instrument per row and one
   parameter or action per column.  It is then possible to poll certain
   parameters by connecting the refresh rate timer to the proper cell.  The
   rest of the GUI is then connected to the table and not to the hardware.  The
   curves shown on the GUI with a monitor, for example, are also stored in the
   table and they are always connected to the refresh rate.  But as they read
   their values from the table, updating them never triggers any reading to the
   hardware.  This architecture ensures that the hardware is called a minimum
   number of times.


1. Initialization of the GUI from Python
========================================

The code from this tutorial is available for download at
:download:`tutgui1.py`.


For the logging application, a `MonitorController` is the most appropriate.
Creating the GUI is then relatively simple:

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
driver mostly automatically, shows the general case.


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


2. Extending and adapting
=========================

This tutorial will show how to make GUIs in the general case.


pyhard2 promotes a strict separation of concerns: writing drivers is not done
with the GUI in mind and conversely, GUI do not target one instrument in
particular, but a class of hardware.


Adapting
--------

It is therefore clear that, in most cases, drivers do not expose the interface
that the GUI requires.  Instead, we may find ourselves in the situation where
the commands exist in the driver under a different name (example taken form the
:mod:`~pyhard2.driver.bronkhorst` drivers).

.. graphviz:: tutgui2.gv

This one-to-one mapping between the two interfaces is expressed rather directly
in Python:

>>> mapper = dict(output="controller.valve_output",
...               measure="direct_reading.fmeasure",
...               setpoint="direct_reading.fsetpoint",
...               pid_gain="controller.PIDKp",
...               pid_integral="controller.PIDKi",
...               pid_derivative="controller.PIDKd")

And it is enough to pass this `mapper` as an extra keyword argument to
`addInstrumentClass` from the previous tutorial.

When no `mapper` is passed, a default one with the form ``dict(zip(labels,
labels)`` is created.

.. note::

   The commands expected by the GUIs are written in the default column headers.
   This is the reason why no mapping was needed in the previous tutorial: the
   GUI automatically displayed the result of `multimeter.measure` in its
   `measure` column.

The `mapper` is actually passed to an instance of a class
:class:`pyhard2.driver.Adapter`, which serves the purpose of changing the
direct calls to the hardware into thread-safe calls leveraging the signal-slot
mechanism from the Qt library.


Extending
---------

Now, the GUIs provided would typically only cover a small part of the
information from the drivers.  In order to have the controller display the
results from more commands, we need to add a column per command and register
the command with the new column.  This is done by calling
:meth:`~models.Controller.registerParameter` or
:meth:`~models.Controller.registerAction` on the controller's model with the
column number as the first argument and the name of the command as the second.
This name can then be used in the `mapper` discussed in the `Adapting`_ section
of this tutorial::

   def createController(config, virtual=False):
      controller = ctrlr.MonitorSetpointController()
      controller.setWindowTitle(u"Controller")
      controller.insertColumn(controller.model().columnCount())
      controller.setHeaderData(ColumnName.Mode, "valve_mode")
      controller.registerParameter(controller.model().columnCount(), "valve_mode")
      return controller

.. note::

   Whether a command should be added as read-only or read-write is decided from
   the status of the column.  For read-only commands,
   :meth:`~models.ColumnReadOnlyModel.setColumnReadOnly` must therefore
   be set accordingly before `registering` the command.


.. seealso::

   Class :class:`pyhard2.driver.Adapter`
      API documentation of the `Adapter` class.


3. Multiple controllers overview in the Dashboard
=================================================

.. module:: pyhard2.ctrlr

The :class:`~dashboard.Dashboard` is used to present an overview over the
controller running.  It may be used, for example, to display the `measure`
information of every controller with an option to change the setpoint, where
applicable.

The `Dashboard` actually launches the controllers, which are then accessible in
the `Controller` menu.  The displays may further be arranged on top of an SVG
image.

:meth:`~dashboard.Dashboard.loadConfig` reads a configuration like the one
introduced above::

   dashboard:
      name: Dashboard
      image: path-to-SVG-file
      label:
         - name: label 1
           pos: [0.1, 0.1]
         - name: label 2
           pos: [0.1, 0.2]

   fluke:
      COM1:
         - name: Fluke 18x
           driver: Fluke18x
           pos: [0.5, 0.5]

The `Dashboard` itself is configured in the `dashboard` section of the YAML
file.  Here as well, `name` is the name of the window.  The file pointed to by
`image` is loaded as the background.  Further `labels` are placed on the image
at the `pos` (positions) indicated in brackets (values between 0.0 and 1.0
given relative to the top-left corner).

After initialization of the `Dashboard`, `loadConfig` proceeds to loading the
controllers.  The configuration file indicates the module name where the
controller is defined (:mod:`pyhard2.ctrlr.fluke` here) and the controller
returned by the :func:`pyhard2.ctrlr.fluke.createController` module-level
function is added to the list of controllers managed by the dashboard, and
started.  Here is the contents of this function:


.. literalinclude:: ../pyhard2/ctrlr/fluke.py
   :pyobject: createController


