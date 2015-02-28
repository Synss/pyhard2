from PyQt5 import QtWidgets, QtCore, QtGui
Qt = QtCore.Qt


class FormatTextDelegate(QtWidgets.QStyledItemDelegate):

    """QStyledItemDelegate formatting the text displayed."""

    def __init__(self, format="%.2f", parent=None):
        super(FormatTextDelegate, self).__init__(parent)
        self._format = format

    def displayText(self, value, locale):
        return self._format % value


class ComboBoxDelegate(QtWidgets.QStyledItemDelegate):

    """QStyledItemDelegate for ComboBox."""

    def __ini__(self, parent=None):
        super(ComboBoxDelegate, self).__init__(parent)

    def setEditorData(self, editor, index):
        if not index.isValid() or index.data() is None:
            return
        editor.setCurrentIndex(index.data())

    def setModelData(self, combobox, model, index):
        if not index.isValid():
            return
        model.setData(index, combobox.currentIndex())


class DoubleSpinBoxDelegate(QtWidgets.QStyledItemDelegate):

    """Item delegate for editing models with a spin box.

    Every property of the spin box can be set on the delegate with the
    methods from QDoubleSpinBox.

    Args:
        spinBox: A spin box prototype to use for editing, defaults to
            `QDoubleSpinBox` if not given.

    Methods:
        decimals()
        setDecimals(prec)
            This property holds the precision of the spin box, in
            decimals.
        minimum()
        setMinimum(min)
            This property holds the minimum value of the spin box.
        maximum()
        setMaximum(max)
            This property holds the maximum value of the spin box.
        setRange(minimum, maximum)
            Convenience function to set the `minimum` and `maximum`
            values with a single function call.
        singleStep()
        setSingleStep(val)
            This property holds the step value.
        prefix()
        setPrefix(prefix)
            This property holds the spin box's prefix.
        suffix()
        setSuffix(suffix)
            This property holds the spin box's suffix.

    """
    def __init__(self, spinBox=None, parent=None):
        super(DoubleSpinBoxDelegate, self).__init__(parent)
        self._spinBox = (QtWidgets.QDoubleSpinBox() if spinBox is None
                         else spinBox)

    def __repr__(self):
        return "%s(spinBox=%r, parent=%r)" % (
            self.__class__.__name__, self._spinBox, self.parent())

    def __getattr__(self, name):
        """Set properties on the spin box."""
        try:
            return object.__getattribute__(self._spinBox, name)
        except AttributeError:
            # Fail with the correct exception.
            return self.__getattribute__(name)

    def createEditor(self, parent, option, index):
        """Return a QDoubleSpinBox."""
        if index.isValid():
            spinBox = self._spinBox.__class__(parent)
            # copy properties
            spinBox.setDecimals(self._spinBox.decimals())
            spinBox.setMaximum(self._spinBox.maximum())
            spinBox.setMinimum(self._spinBox.minimum())
            spinBox.setPrefix(self._spinBox.prefix())
            spinBox.setSingleStep(self._spinBox.singleStep())
            spinBox.setSuffix(self._spinBox.suffix())
            spinBox.editingFinished.connect(self._commitAndCloseEditor)
            return spinBox
        else:
            return super(DoubleSpinBoxDelegate, self).createEditor(
                parent, option, index)

    def setEditorData(self, spinBox, index):
        """Set spin box value to `index.data()`."""
        if index.isValid():
            try:
                spinBox.setValue(index.data())
            except TypeError:
                pass

    def setModelData(self, spinBox, model, index):
        """Set model data to `spinBox.value()`."""
        if index.isValid():
            model.setData(index, spinBox.value())
        else:
            super(DoubleSpinBoxDelegate, self).setModelData(
                spinBox, model, index)

    def _commitAndCloseEditor(self):
        """Commit data and close editor."""
        self.commitData.emit(self.sender())
        self.closeEditor.emit(self.sender(), self.NoHint)


class ButtonDelegate(QtWidgets.QStyledItemDelegate):

    """Item delegate for editing models with a button.

    Args:
        button: The button prototype to use for editing, defaults to
            `QPushButton` if not given.

    """
    def __init__(self, button=None, parent=None):
        super(ButtonDelegate, self).__init__(parent)
        self._btn = QtWidgets.QPushButton() if button is None else button
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
        model.setData(index, editor.isChecked())

    def setEditorData(self, editor, index):
        editor.setChecked(index.data() if index.data() else Qt.Unchecked)

    def paint(self, painter, option, index):
        self._btn.setChecked(index.data() if index.data() else Qt.Unchecked)
        self._btn.setGeometry(option.rect)
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        pixmap = self._btn.grab()
        painter.drawPixmap(option.rect.x(), option.rect.y(), pixmap)

    def editorEvent(self, event, model, option, index):
        """Change the state of the editor and the data in the model when
        the user presses the left mouse button, Key_Space or Key_Select
        iff the cell is editable.

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
