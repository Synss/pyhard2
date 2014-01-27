.. module:: pyhard2.ctrlr


GUI Tutorial 3: Multiple controllers overview in the Dashboard
==============================================================


The :class:`~dashboard.Dashboard` is used to present an overview over the
controller running.  It may be used, for example, to display the `measure`
information of every controller with an option to change the setpoint, where
applicable.

The `Dashboard` actually launches the controllers, which are then accessible in
the `Controller` menu.  The displays may further be arranged on top of an SVG
image.

:meth:`~dashboard.Dashboard.loadConfig` reads a configuration like the one
introduced in :doc:`tutgui1`::

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


