""" Enums for pyhard2.ctrlr.qt4 """

from PyQt4 import QtCore
Qt = QtCore.Qt


class ColumnName(object):

    """Enum containing model column names."""

    MeasureColumn = 0
    SetpointColumn = 1
    OutputColumn = 2
    PidGainColumn = 3
    PidIntegralColumn = 4
    PidDerivativeColumn = 5
    UserColumn = 6


class UserRole(object):

    """Enum containing model user roles."""

    CommandType = Qt.UserRole + 2
    CommandName = Qt.UserRole + 3
    PollingCheckStateRole = Qt.UserRole + 4


