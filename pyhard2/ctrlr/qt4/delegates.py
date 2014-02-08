""" Delegates for pyhard2.ctrlr.qt4 """

from PyQt4 import QtCore, QtGui
Slot, Signal = QtCore.pyqtSlot, QtCore.pyqtSignal
Qt = QtCore.Qt


class NumericDelegate(QtGui.QStyledItemDelegate):

    """A model delegate exposing a :class:`QtGui.QDoubleSpinBox`."""

    def __init__(self, parent=None):
        super(NumericDelegate, self).__init__(parent)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.parent())

    def createEditor(self, parent, option, index):
        """Reimplemented from :class:`QtGui.QStyledItemDelegate`."""
        if index.isValid():
            item = index.model().itemFromIndex(index)
            editor = QtGui.QDoubleSpinBox(parent)
            if item.minimum() is not None:
                editor.setMinimum(item.minimum())
            if item.maximum() is not None:
                editor.setMaximum(item.maximum())
            editor.editingFinished.connect(self._commitAndCloseEditor)
            return editor
        else:
            return super(NumericDelegate, self).createEditor(
                parent, option, index)

    def setEditorData(self, editor, index):
        """Reimplemented from :class:`QtGui.QStyledItemDelegate`."""
        if index.isValid():
            value = index.data()
            editor.setValue(value if value is not None else 0.0)
        else:
            super(NumericDelegate, self).setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        """Reimplemented from QtGui.QStyledItemDelegate."""
        if index.isValid():
            model.setData(index, editor.value())
        else:
            super(NumericDelegate, self).setModelData(editor, model, index)

    def _commitAndCloseEditor(self):
        """Commit data and close editor."""
        self.commitData.emit(self.sender())
        self.closeEditor.emit(self.sender(), self.NoHint)


class ButtonDelegate(QtGui.QStyledItemDelegate):

    """A model delegate handling boolean-type buttons."""

    def __init__(self, button=None, parent=None):
        super(ButtonDelegate, self).__init__(parent)
        self._btn = QtGui.QPushButton() if button is None else button
        self._btn.setParent(parent)
        self._btn.hide()        

    def __repr__(self):
        return "%s(button=%r, parent=%r)" % (
            self.__class__.__name__, self._btn, self.parent())

    def sizeHint(self, option, index):
        return super(ButtonDelegate, self).sizeHint(option, index)

    def createEditor(self, parent, option, index):
        return None

    def setModelData(self, editor, model, index):
        model.setData(index, editor.isChecked(), role=Qt.CheckStateRole)

    def setEditorData(self, editor, index):
        editor.setChecked(index.checkState() if index.checkState() is not None
                         else Qt.Unchecked)

    def paint(self, painter, option, index):
        self._btn.setChecked(index.data(role=Qt.CheckStateRole)
                             if index.data(role=Qt.CheckStateRole) is not None
                             else Qt.Unchecked)
        self._btn.setGeometry(option.rect)
        if option.state & QtGui.QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        pixmap = QtGui.QPixmap.grabWidget(self._btn)
        painter.drawPixmap(option.rect.x(), option.rect.y(), pixmap)

    def editorEvent(self, event, model, option, index):
        """Change the state of the editor and the data in the model when
        the user presses the left mouse button, Key_Space or Key_Select
        if the cell is editable.

        """
        if (int(index.flags()) & Qt.ItemIsEditable and
            (event.type() in (QtCore.QEvent.MouseButtonRelease,
                              QtCore.QEvent.MouseButtonDblClick) and
             event.button() == Qt.LeftButton) or
            (event.type() == QtCore.QEvent.KeyPress and
             event.key() in (Qt.Key_Space, Qt.Key_Select))):
                self._btn.toggle()
                self.setModelData(self._btn, model, index)
                self.commitData.emit(self._btn)
                return True
        return False        


