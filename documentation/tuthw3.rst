.. module:: pyhard2.driver


Driver Tutorial 3: Parameters and actions
=========================================

The code from this tutorial is available for download at :download:`tuthw3.py`.


The manual to the meter introduced in :doc:`tuthw1` further shows that it is
possible to simulate button presses with commands like "`SF {key code}`", where
`{key code}` is an integer between 10 and 30.  We could define twenty commands
"SF 10", "SF 11", etc. or add an ``if 10 <= param.getcmd <= 30`` condition in
the protocol, but that would either be a lot of work or a fragile solution.
Instead, we add these commands using the :meth:`~Subsystem.add_action_by_name`
method from `Subsystem`.  The completed subsystem now looks like:


.. literalinclude:: tuthw3.py
   :pyobject: FlukeSubsystem

with the rest of the classes defined as in :doc:`tuthw2`.

>>> import pyhard2.driver as drv
>>> from tuthw3 import Fluke18x
>>> multimeter = Fluke18x(drv.Serial())
>>> print(multimeter)
path                                    	  type   	doc
========================================	=========	===
measure                                 	Parameter	None
press_button_Hz                         	Action	None
press_button_auto_hold                  	Action	None
press_button_backlight                  	Action	None
press_button_blue                       	Action	None
press_button_calibration                	Action	None
press_button_cancel                     	Action	None
press_button_down_arrow                 	Action	None
press_button_fast_min_max               	Action	None
press_button_hold                       	Action	None
press_button_logging                    	Action	None
press_button_min_max                    	Action	None
press_button_range                      	Action	None
press_button_rel                        	Action	None
press_button_save                       	Action	None
press_button_setup                      	Action	None
press_button_shift                      	Action	None
press_button_up_arrow                   	Action	None
press_button_wake_up                    	Action	None
unit                                    	Parameter	None


.. topic::  Parameters and actions

   Interactions with the hardware occur via parameters or actions.

   Parameters
      are `set` or `gotten`.  They usually return a value and are better
      expressed by a noun or a quantity like `temperature`, `setpoint`, `power`
      or `duty_cycle`.

   Actions
      are better expressed with a verb like `reset`, `trigger`, or `clear`.


The :meth:`~Subsystem.add_action_by_name` and its
:meth:`~Subsystem.add_parameter_by_name` pendant can be used to
semi-automatically generate subsystems from various formats like Excel
workbooks.  See how in :doc:`tuthw4`.  Or go directly include the driver in a
:doc:`tutgui1`.


.. seealso::

   Class :class:`pyhard2.driver.Parameter`
      API documentation of the `Parameter` class.

   Class :class:`pyhard2.driver.Action`
      API documentation of the `Action` class.
