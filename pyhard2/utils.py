from collections import namedtuple


def record(func): return namedtuple(func.__name__, func.__code__.co_varnames)


