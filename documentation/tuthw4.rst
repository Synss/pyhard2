.. module:: pyhard2.driver


Driver Tutorial 4: Semi-automatic driver generation
===================================================


The code from this tutorial is available for download at :download:`tuthw3.py`
and :download:`tuthw4.ods`.


The two methods :meth:`~Subsystem.add_parameter_by_name` and
:meth:`~Subsystem.add_action_by_name` introduced in the previous tutorial
:doc:`tuthw3` are very powerful.  They can be used to generate `Subsystems`
from outside Python.  Here, we complete our multimeter driver using a
spreadsheet program (like LibreOffice).

The sheet is available for download and looks approximately like the table:

.. table:: FlukeSubsystem

   =========  ==============  =======  =========
   type       name            command  read only
   =========  ==============  =======  =========
   Parameter  identification  ID           FALSE
   Action     default_setup   DS
   Action     reset           RI
   =========  ==============  =======  =========

The file may be opened using `ezodf <http://pythonhosted.org/ezodf>`_::

   import ezodf
   from tuthw3 import Fluke18x as FlukeTutHw3


   class Fluke18x(FlukeTutHw3):

      def __init__(self, socket, protocol=None):
         super(Fluke18x, self).__init__(socket, protocol)
         spreadsheet = ezodf.opendoc("tuthw4.ods")
         self.init_from_spreadsheet(spreadsheet)


The function :func:`init_from_spreadsheet` is rather general and its first
argument is an opened workbook.  The second argument optional but
:func:`globals` may be used here to give access to `setter_func` and
`getter_func` defined in the module.

Each worksheet in the spreadsheet is read in turn and the header is assumed to
be in the first row.  The other rows contain the parameters and actions of the
subsystem.

>>> meter = Fluke18x(drv.Serial())  # that we just created above
>>> meter.main = meter.fluke_subsystem  # set default subsystem

Three new commands have been added as confirmed by:

>>> for line in meter.__str__().splitlines():
...     if not line.startswith("press"):
...         print(line)
...
path                                    	  type   	doc
========================================	=========	===
default_setup                           	Action	None
identification                          	Parameter	None
measure                                 	Parameter	None
reset                                   	Action	None
unit                                    	Parameter	None


This demonstrates the flexibility of pyhard2 and the fact that the largest part
of the code constituting pyhard2 drivers *does not actually need to be coded*.


This series of tutorials demonstrated most of pyhard2's features.  The next
series introduces graphical user interfaces starting with the four lines
necessary to log the measurements from our meter into a :doc:`tutgui1`.

(Four lines excluding PyQt4 boilerplate code.)


.. seealso::

   Class :class:`pyhard2.driver.Subsystem`
      API documentation of the `Subsystem` class.

