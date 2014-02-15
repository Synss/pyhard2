"""
Parse Open Document Format for Office Applications format.

Parse the spreadsheet format with ezodf.

"""

import sys as _sys
import ezodf
import pyhard2.driver as drv


def un_camel(s):
    """Convert CamelCase to camel_case."""
    return s[0].lower() + "".join("_" + c.lower() if c.isupper() else c
                                  for c in s[1:])


def _subsystem_from_sheet(sheet, module):
    """ Initialize a subsystem from an ODF document. """
    subsystem = type(sheet.name, (module.get("Subsystem", drv.Subsystem),), {})
    for n, row in enumerate(sheet.rows()):
        if n is 0:
            # First row contains headers
            col_names = [cell.value for cell in row if cell.value is not None]
            continue
        col_values = [cell.value for cell in row]
        if (not [value for value in col_values if value is not None] or
            not col_names):
            continue
        cmd_args = dict(zip(col_names, col_values))
        cmd_name = cmd_args.pop("name")
        cmd_type = cmd_args.pop("type", "parameter")
        for func_name in "getter_func setter_func".split():
            kw = cmd_args.get(func_name)
            if kw is not None:
                cmd_args[func_name] = eval(kw, module)
        if cmd_type.strip().lower() == "action":
            # Add action
            subsystem.add_action_by_name(cmd_name, **cmd_args)
        else:
            # default to adding as parameter
            subsystem.add_parameter_by_name(cmd_name, **cmd_args)
    return subsystem


def subsystems_factory(filename):
    """ Create `Subsystems` from an ODF document.

        The first row of each sheet must contain headers labeled with
        the name of the parameters passed to the init of `Parameter` and
        `Action`.

        Parameters
        ----------
        filename : filename
            Filename of the spreadsheet.

        Returns
        -------
        dict(str, Subsystem class)
            `Subsystem` name: `Subsystem` class pairs.  The Subsystems
            must be instantiated by the caller.

        Examples
        --------
        >>> instrument = drv.Instrument()
        >>> for name, subsystem in subsystems_factory(filename).iteritems():
        ...     setattr(instrument, "filename.ods",  # actual path
        ...             subsystem(drv.ProtocolLess(None, async=False)))

        Notes
        -----
        - The prototype used for the new subsystems will be either the
          class named `Subsystem` in the caller module if it exists, or
          `drv.Subsystem`.
        - Expressions in the `getter_func` and `setter_func` columns
          will be sent to `eval`.  This could be used to execute
          arbitrary code.

    """
    module = _sys._getframe(1).f_globals
    workbook = ezodf.opendoc(filename)
    return {un_camel(sheet.name):
            _subsystem_from_sheet(sheet, module)
            for sheet in workbook.sheets}


if __name__ == "__main__":
    from pyhard2.driver.watlow import Series988
    instrument = Series988(drv.Serial)
    print(instrument)

