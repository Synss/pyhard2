.. module:: pyhard2.ctrlr.qt4


GUI Tutorial 2: Extending and adapting
======================================


Whereas the :doc:`tutgui1` demonstrates a simple way to create a GUI.  This
tutorial will show how to make GUIs in the general case.


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


The next tutorial :doc:`tutgui3` shows how to create a single user interface
for an ensemble of different controllers.


.. seealso::

   Class :class:`pyhard2.driver.Adapter`
      API documentation of the `Adapter` class.
