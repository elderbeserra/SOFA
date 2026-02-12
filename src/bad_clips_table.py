from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractScrollArea,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class BadClipsWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.title = 'Removed clips'
        self.default_color: QBrush | None = None
        self.initUI()
        self.currentRow: int = 0

    def initUI(self) -> None:
        self.setWindowTitle(self.title)
        self.createTable()
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.tableWidget)
        self.setLayout(self.main_layout)

    def createTable(self) -> None:
        self.tableWidget = QTableWidget()
        self.tableWidget.setRowCount(1)
        self.tableWidget.setColumnCount(4)
        self.tableWidget.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.tableWidget.setHorizontalHeaderLabels(['begin', 'end', 'duration', ''])
        self.tableWidget.resizeColumnsToContents()

    def new_mark(self, time: float, mode: bool) -> None:
        index = self.currentRow
        if not mode:
            start_or_stop = 0
            index = self.tableWidget.rowCount() - 1
            self.tableWidget.setItem(index, 1, QTableWidgetItem('...'))
            duration = '...'
            if not self.default_color:
                self.default_color = self.tableWidget.item(index, 1).background()
            self.tableWidget.insertRow(index + 1)
        else:
            start_or_stop = 1
            self.currentRow += 1
            begin = float(self.tableWidget.item(index, 0).text())
            duration = str(round(time - begin, 2))
        timeItem = QTableWidgetItem(str(time))
        self.tableWidget.setItem(index, start_or_stop, timeItem)
        self.tableWidget.setItem(index, 2, QTableWidgetItem(duration))
        delButton = QPushButton()
        delButton.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        delButton.clicked.connect(self.deleteRow)
        self.tableWidget.setCellWidget(index, 3, delButton)
        self.tableWidget.scrollToItem(timeItem)
        self.tableWidget.resizeColumnsToContents()
        self.set_row_color(index, mode)

    @pyqtSlot()
    def deleteRow(self) -> None:
        button = self.sender()
        if button:
            row = self.tableWidget.indexAt(button.pos()).row()
            self.tableWidget.removeRow(row)
            self.currentRow -= 1

    def set_row_color(self, index: int, mode: bool) -> None:
        if not mode:
            self.__row_colors(index, QColor(64, 249, 107))
        else:
            self.__row_colors(index, self.default_color)

    def get_marks(self) -> list[list[str]]:
        t = self.tableWidget
        marks = [
            [self.get_item_marks(i, j) for j in range(t.columnCount() - 1)]
            for i in range(t.rowCount() - 1)
        ]
        return marks

    def get_item_marks(self, i: int, j: int) -> str:
        try:
            return self.tableWidget.item(i, j).text()
        except Exception:
            return 'ERROR_INVALID_VALUE'

    def __row_colors(self, i: int, color: QColor | QBrush | None) -> None:
        for ii in range(self.tableWidget.columnCount() - 1):
            self.tableWidget.item(i, ii).setBackground(color)
