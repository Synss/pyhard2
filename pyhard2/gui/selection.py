import StringIO as _StringIO
import csv as _csv

from PyQt5 import QtWidgets, QtCore, QtGui


class ItemSelectionModel(QtCore.QItemSelectionModel):

    """QItemSelectionModel with copy/paste and a part of the
    QTableWidget interface.

    """
    def __init__(self, model, parent=None):
        super(ItemSelectionModel, self).__init__(model, parent)

    def currentRow(self):
        """Return the row of the current item."""
        return self.currentIndex().row()

    def currentColumn(self):
        """Return the column of the current item."""
        return self.currentIndex().column()

    def _parentItem(self):
        """Return the parent of the current item."""
        item = self.model().itemFromIndex(self.currentIndex()).parent()
        return item if item else self.model().invisibleRootItem()

    def insertRow(self):
        """Insert an empty row into the table at the current row."""
        parent = self._parentItem()
        parent.insertRow(
            self.currentRow(),
            [QtGui.QStandardItem() for __ in range(parent.columnCount())])

    def insertColumn(self):
        """Insert an empty column into the table at the current column."""
        parent = self._parentItem()
        parent.insertColumn(
            self.currentColumn(),
            [QtGui.QStandardItem() for __ in range(parent.rowCount())])

    def removeRows(self):
        """Remove the selected rows."""
        currentIndex = self.currentIndex()
        selection = self.selectedRows()
        if not selection:
            selection = [currentIndex]
        parent = self._parentItem()
        rowCount = parent.rowCount()
        for row in (index.row() for index in selection):
            parent.removeRow(row)
        parent.setRowCount(rowCount)

    def removeColumns(self):
        """Remove the selected columns."""
        currentIndex = self.currentIndex()
        selection = self.selectedColumns()
        if not selection:
            selection = [currentIndex]
        parent = self._parentItem()
        columnCount = parent.columnCount()
        for column in (index.column() for index in selection):
            parent.removeColumn(column)
        parent.setColumnCount(columnCount)

    def copy(self):
        """Copy the values in the selection to the clipboard."""
        previous = QtCore.QModelIndex()
        fields = []
        for index in sorted(self.selectedIndexes()):
            if index.row() is previous.row():
                fields[-1].append(index.data())
            else:
                fields.append([index.data()])
            previous = index
        csvfile = _StringIO.StringIO()
        writer = _csv.writer(csvfile)
        writer.writerows(fields)
        QtWidgets.QApplication.clipboard().setText(csvfile.getvalue())

    def paste(self):
        """Paste values in the clipboard at the current item.

        Raises:
            IndexError: if the data in the clipboard does not fit in the
                model.

        """
        currentIndex = self.currentIndex()
        parent = self._parentItem()
        csvfile = _StringIO.StringIO(QtWidgets.QApplication.clipboard().text())
        try:
            dialect = _csv.Sniffer().sniff(csvfile.read(1024))
        except _csv.Error:
            return
        csvfile.seek(0)
        reader = _csv.reader(csvfile, dialect)
        for i, line in enumerate(reader):
            if currentIndex.column() + len(line) > parent.columnCount():
                raise IndexError
            for j, text in enumerate(line):
                parent.setChild(currentIndex.row() + i,
                                currentIndex.column() + j,
                                QtGui.QStandardItem(text))
