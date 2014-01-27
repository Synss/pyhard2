"""
pyhard2.ctrlr module
====================

This module contains classes used to implement the graphical user
interfaces.

"""


__package__ = "pyhard2.ctrlr"
import pyhard2.rsc
from .qt4 import *


def cmdline():
    """Parse command line arguments to initialize a Controller."""
    import argparse
    parser = argparse.ArgumentParser(description="Start GUI")
    parser.add_argument('-v', '--virtual', action="store_true")
    parser.add_argument('file', type=file, nargs="?")
    parser.add_argument('config', nargs="*")
    opts = parser.parse_args()
    if opts.file is None:
        opts = parser.parse_args(["--virtual"])
    else:
        import yaml
        opts.config = yaml.load(opts.file)
    return opts


