import pyhard2.driver as drv


class HardwareError(drv.HardwareError): pass

class DriverError(drv.DriverError): pass


class Ieee488CommunicationProtocol(drv.CommunicationProtocol):

    """Communication protocol for the IEEE 488.1 standard."""

    def read(self, context):
        self._socket.write("*{cmd}?\n".format(cmd=context.reader))
        return self._socket.readline().strip()

    def write(self, context):
        if context.value is not None:
            msg = "*{cmd} {val}\n".format(cmd=context.writer,
                                          val=context.value)
        else:
            msg = "*{cmd}\n".format(cmd=context.writer)
        self._socket.write(msg)


class ScpiSubsystem(drv.Subsystem):

    """`Subsystem` with a mnemonic."""

    def __init__(self, mnemonic, parent=None):
        super().__init__(parent)
        self.mnemonic = mnemonic


class ScpiCommunicationProtocol(drv.CommunicationProtocol):

    """SCPI protocol."""

    def __init__(self, socket, parent=None):
        super().__init__(socket, parent)

    @staticmethod
    def _scpiPath(context):
        return ":".join(subsystem.mnemonic
                        for subsystem in reversed(context.path)
                        if isinstance(subsystem, ScpiSubsystem))

    @staticmethod
    def _scpiStrip(path):
        return "".join((c for c in path if c.isupper() or not c.isalpha()))

    def read(self, context):
        msg = "{path}?\n".format(
            path=self._scpiStrip(":".join((self._scpiPath(context),
                                           context.reader))))
        self._socket.write(msg)
        return self._socket.readline()

    def write(self, context):
        if context.value is True:
            context.value = "ON"
        elif context.value is False:
            context.value = "OFF"
        msg = "{path} {value}\n".format(
            path=self._scpiStrip(":".join((self._scpiPath(context),
                                           context.writer))),
            value=context.value)
        self._socket.write(msg)
