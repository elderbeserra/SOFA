from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QBrush, QColor, QPixmap
from PyQt5.QtWidgets import (
    QAbstractScrollArea,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

THUMBNAIL_SIZE = 48
THUMB_COL, BEGIN_COL, END_COL, DURATION_COL, DELETE_COL = 0, 1, 2, 3, 4


class BadClipsWidget(QWidget):
    thumbnail_requested = pyqtSignal(int, float)
    marks_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.title = 'Clips to export'
        self.default_color: QBrush | None = None
        self._video_path: str = ''
        self._history: list[list[list[str]]] = []
        self._history_index: int = -1
        self._block_item_changed: bool = False
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
        self.tableWidget.setColumnCount(5)
        self.tableWidget.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.tableWidget.setHorizontalHeaderLabels([
            'Preview', 'begin', 'end', 'duration', ''
        ])
        self.tableWidget.horizontalHeader().setSectionResizeMode(
            THUMB_COL, QHeaderView.Fixed
        )
        self.tableWidget.setColumnWidth(THUMB_COL, THUMBNAIL_SIZE + 4)
        self.tableWidget.itemChanged.connect(self._on_item_changed)
        self.tableWidget.resizeColumnsToContents()

    def set_video_path(self, path: str) -> None:
        self._video_path = path or ''

    def _get_complete_marks(self) -> list[list[str]]:
        """Return only rows with valid begin, end, duration (no in-progress row)."""
        t = self.tableWidget
        out: list[list[str]] = []
        for i in range(t.rowCount() - 1):
            try:
                dur = self.get_item_marks(i, DURATION_COL)
                if dur in ('...', 'ERROR_INVALID_VALUE', ''):
                    continue
                float(dur)
                out.append([
                    self.get_item_marks(i, BEGIN_COL),
                    self.get_item_marks(i, END_COL),
                    dur,
                ])
            except (ValueError, TypeError):
                continue
        return out

    def _push_state(self) -> None:
        state = self._get_complete_marks()
        if self._history_index < len(self._history) - 1:
            self._history = self._history[: self._history_index + 1]
        self._history.append(state)
        self._history_index = len(self._history) - 1

    def undo(self) -> bool:
        if self._history_index <= 0:
            return False
        self._history_index -= 1
        self._block_item_changed = True
        self.set_marks(self._history[self._history_index])
        self._block_item_changed = False
        self.marks_changed.emit()
        return True

    def redo(self) -> bool:
        if self._history_index >= len(self._history) - 1:
            return False
        self._history_index += 1
        self._block_item_changed = True
        self.set_marks(self._history[self._history_index])
        self._block_item_changed = False
        self.marks_changed.emit()
        return True

    def set_marks(self, marks: list[list[str]]) -> None:
        """Restore table from list of [begin, end, duration] (for undo/redo)."""
        self._block_item_changed = True
        t = self.tableWidget
        t.setRowCount(len(marks) + 1)
        for i, (begin, end, duration) in enumerate(marks):
            thumb_label = QLabel()
            thumb_label.setAlignment(Qt.AlignCenter)
            t.setCellWidget(i, THUMB_COL, thumb_label)
            for col, val in enumerate([begin, end, duration], BEGIN_COL):
                it = QTableWidgetItem(val)
                if col in (BEGIN_COL, END_COL):
                    it.setFlags(it.flags() | Qt.ItemIsEditable)
                t.setItem(i, col, it)
            del_btn = QPushButton()
            del_btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
            del_btn.clicked.connect(self.deleteRow)
            t.setCellWidget(i, DELETE_COL, del_btn)
            self.__row_colors(i, self.default_color or QColor(255, 255, 255))
        self.currentRow = len(marks)
        self._block_item_changed = False
        self.tableWidget.resizeColumnsToContents()

    def set_thumbnail(self, row: int, pixmap: QPixmap | None) -> None:
        if row < 0 or row >= self.tableWidget.rowCount():
            return
        scaled = pixmap.scaled(
            THUMBNAIL_SIZE,
            THUMBNAIL_SIZE,
            aspectRatioMode=Qt.KeepAspectRatio,
            transformMode=Qt.SmoothTransformation,
        ) if pixmap and not pixmap.isNull() else QPixmap()
        label = QLabel()
        label.setPixmap(scaled)
        label.setAlignment(Qt.AlignCenter)
        self.tableWidget.setCellWidget(row, THUMB_COL, label)

    def new_mark(self, time: float, mode: bool) -> None:
        index = self.currentRow
        if not mode:
            start_or_stop = BEGIN_COL
            index = self.tableWidget.rowCount() - 1
            self.tableWidget.setItem(index, END_COL, QTableWidgetItem('...'))
            duration = '...'
            if not self.default_color:
                self.default_color = self.tableWidget.item(index, END_COL).background()
            self.tableWidget.insertRow(index + 1)
        else:
            start_or_stop = END_COL
            self._push_state()
            self.currentRow += 1
            begin = float(self.tableWidget.item(index, BEGIN_COL).text())
            duration = str(round(time - begin, 2))
            mid_time = (begin + time) / 2.0
            self.thumbnail_requested.emit(index, mid_time)
        timeItem = QTableWidgetItem(str(round(time, 2)))
        if start_or_stop in (BEGIN_COL, END_COL):
            timeItem.setFlags(timeItem.flags() | Qt.ItemIsEditable)
        self.tableWidget.setItem(index, start_or_stop, timeItem)
        self.tableWidget.setItem(index, DURATION_COL, QTableWidgetItem(duration))
        delButton = QPushButton()
        delButton.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        delButton.clicked.connect(self.deleteRow)
        self.tableWidget.setCellWidget(index, DELETE_COL, delButton)
        self.tableWidget.scrollToItem(timeItem)
        self.tableWidget.resizeColumnsToContents()
        self.set_row_color(index, mode)
        self.marks_changed.emit()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._block_item_changed or item.column() not in (BEGIN_COL, END_COL):
            return
        row = item.row()
        if row >= self.tableWidget.rowCount() - 1:
            return
        try:
            begin = float(self.tableWidget.item(row, BEGIN_COL).text())
            end = float(self.tableWidget.item(row, END_COL).text())
            if begin < end:
                dur = str(round(end - begin, 2))
                self._block_item_changed = True
                self.tableWidget.item(row, DURATION_COL).setText(dur)
                self._block_item_changed = False
                self.marks_changed.emit()
        except (ValueError, TypeError, AttributeError):
            pass

    @pyqtSlot()
    def deleteRow(self) -> None:
        button = self.sender()
        if button:
            row = self.tableWidget.indexAt(button.pos()).row()
            if 0 <= row < self.tableWidget.rowCount() - 1:
                self._push_state()
                self.tableWidget.removeRow(row)
                self.currentRow -= 1
                self.marks_changed.emit()

    def set_row_color(self, index: int, mode: bool) -> None:
        if not mode:
            self.__row_colors(index, QColor(64, 249, 107))
        else:
            self.__row_colors(index, self.default_color)

    def get_marks(self) -> list[list[str]]:
        t = self.tableWidget
        marks = [
            [
                self.get_item_marks(i, BEGIN_COL),
                self.get_item_marks(i, END_COL),
                self.get_item_marks(i, DURATION_COL),
            ]
            for i in range(t.rowCount() - 1)
            if self.get_item_marks(i, DURATION_COL) not in ('...', 'ERROR_INVALID_VALUE', '')
        ]
        return marks

    def get_item_marks(self, i: int, j: int) -> str:
        try:
            it = self.tableWidget.item(i, j)
            return it.text() if it is not None else 'ERROR_INVALID_VALUE'
        except Exception:
            return 'ERROR_INVALID_VALUE'

    def __row_colors(self, i: int, color: QColor | QBrush | None) -> None:
        for j in (BEGIN_COL, END_COL, DURATION_COL):
            it = self.tableWidget.item(i, j)
            if it is not None:
                it.setBackground(color)
