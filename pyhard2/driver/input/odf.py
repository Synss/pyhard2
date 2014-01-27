"""
Parse Open Document Format for Office Applications format.

Parse the spreadsheet format with ezodf.

"""

import ezodf
import pyhard2.driver as drv


def un_camel(s):
    """Convert CamelCase to camel_case."""
    return s[0].lower() + "".join("_" + c.lower() if c.isupper() else c
                                  for c in s[1:])


def subsystem_from_sheet(sheet, subsystem, module=None):
    """ Initialize a subsystem from an ODF document.

        The first row of the sheet must contain headers labeled with the name
        of the parameters passed to the init of `Parameter` and `Action`.

        Parameters
        ----------
        sheet : workbook.sheet
        subsystem : Subsystem
            The subsystem to initialize.
        module : dict, optional
            The module of the caller.  Provides access to the local functions
            defined with the driver.


        .. warning::
            Expressions in the `getter_func` and `setter_func`
            columns will be sent to `eval`.  This could be used to
            execute arbitrary code.

    """
    module = globals() if module is None else module

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


def instrument_from_workbook(filename, instrument, protocol, module=None):
    """ Initialize an instrument from an ODF document.

        Parameters
        ----------
        filename : filename
            Filename of the spreadsheet.
        instrument : Instrument
        protocol : Protocol
        module : dict, optional
            The `globals()` dictionary may be parsed here to give access
            to functions defined in the caller module.
            If a class named `Subsystem` is defined in `module`, it will
            be used to initialize the new subsystems.

    """
    module = globals() if module is None else module
    workbook = ezodf.opendoc(filename)
    for sheet in workbook.sheets:
        try:
            # Get subsystem from instrument
            subsystem = vars(instrument)[sheet.name]
        except (TypeError, KeyError):
            # or create a new one if it does not exist
            subsystem = type(sheet.name,
                             (module.get("Subsystem", drv.Subsystem),),
                             {})(protocol)
        subsystem_from_sheet(sheet, subsystem, module)
        setattr(instrument, un_camel(sheet.name), subsystem)


if __name__ == "__main__":
    from pyhard2.driver.watlow import Series988
    instrument = Series988(drv.Serial)
    print(instrument)

