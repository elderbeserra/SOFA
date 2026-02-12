from collections.abc import Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PyQt5.QtWidgets import QSizePolicy, QWidget


class HlightSliderTipsWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.video_len: int = 8
        self.useYellow: bool = False
        self.initUI()

    def initUI(self) -> None:
        self.setMinimumSize(170, 30)
        self.colorsArray: Sequence[int] = []
        self.value: int = 0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def setColorsArray(
        self, colorsArray: Sequence[int], useYellow: bool = False
    ) -> None:
        self.colorsArray = colorsArray
        self.setRange(len(colorsArray))
        self.useYellow = useYellow

    def setValue(self, value: int) -> None:
        self.value = value
        self.repaint()

    def paintEvent(self, e: QPaintEvent) -> None:
        qp = QPainter()
        qp.begin(self)
        self.drawWidget(qp)
        qp.end()

    def setRange(self, r: int) -> None:
        self.video_len = r
        self.repaint()

    def drawWidget(self, qp: QPainter) -> None:
        # initializing
        font = QFont('Serif', 7, QFont.Light)
        qp.setFont(font)
        size = self.size()
        w = size.width()
        h = size.height()
        step = 1

        # setting background
        pen = QPen(QColor(20, 20, 20), 1, Qt.SolidLine)
        qp.setPen(pen)
        qp.setBrush(Qt.NoBrush)
        qp.drawRect(0, 0, w - 1, h - 1)

        if not self.useYellow:
            for curr, diff_value in enumerate(self.colorsArray):
                till = curr + step
                # red - requires attention
                if diff_value != 0:
                    qp.setPen(QColor(184, 0, 0))
                    qp.setBrush(QColor(184, 0, 0))
                else:
                    qp.setPen(QColor(80, 80, 80))
                    qp.setBrush(QColor(80, 80, 80))

                # drawRect(x1,y1,w,h), which here is...
                qp.drawRect(curr, 0, till, h)
                if diff_value != 0:
                    pen = QPen(QColor(255, 0, 0), 1, Qt.SolidLine)
                else:
                    pen = QPen(QColor(80, 80, 80), 1, Qt.SolidLine)

                qp.setPen(pen)
        else:
            for curr, diff_value in enumerate(self.colorsArray):
                till = curr + step
                # yellow - no register by one of the (or both) algorithms
                if diff_value == 2:
                    qp.setPen(QColor(255, 255, 184))
                    qp.setBrush(QColor(255, 255, 184))
                # red
                elif diff_value == 1:
                    qp.setPen(QColor(184, 0, 0))
                    qp.setBrush(QColor(184, 0, 0))

                # drawRect(x1,y1,w,h), which here is...
                qp.drawRect(curr, 0, till, h)
                if diff_value == 2:
                    pen = QPen(QColor(255, 255, 0), 1, Qt.SolidLine)
                elif diff_value == 1:
                    pen = QPen(QColor(255, 0, 0), 1, Qt.SolidLine)
                qp.setPen(pen)


class HlightRmClipsWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.video_len: int = 8
        self.isRemoved: bool = False
        self.initUI()

    def initUI(self) -> None:
        self.setMinimumSize(170, 30)
        self.value: int = 0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def setValue(self, value: int) -> None:
        self.value = value
        self.repaint()

    def paintEvent(self, e: QPaintEvent) -> None:
        qp = QPainter()
        qp.begin(self)
        self.drawWidget(qp)
        qp.end()

    def setRange(self, r: int) -> None:
        self.video_len = r
        self.repaint()

    def toggleRm(self) -> None:
        self.isRemoved = not self.isRemoved

    def drawWidget(self, qp: QPainter) -> None:
        MAX_CAPACITY = 8
        OVER_CAPACITY = self.video_len
        font = QFont('Serif', 7, QFont.Light)
        qp.setFont(font)
        size = self.size()
        w = size.width()
        h = size.height()
        till = int(((w / OVER_CAPACITY) * self.value))
        full = int(((w / OVER_CAPACITY) * MAX_CAPACITY))
        if self.isRemoved:
            qp.setPen(QColor(255, 255, 255))
            qp.setBrush(QColor(255, 255, 184))
            qp.drawRect(0, 0, full, h)
            qp.setPen(QColor(255, 175, 175))
            qp.setBrush(QColor(255, 175, 175))
            qp.drawRect(full, 0, till - full, h)
        else:
            qp.setPen(QColor(255, 255, 255))
            qp.setBrush(QColor(255, 255, 184))
            qp.drawRect(0, 0, till, h)
        pen = QPen(QColor(20, 20, 20), 1, Qt.SolidLine)
        qp.setPen(pen)
        qp.setBrush(Qt.NoBrush)
        qp.drawRect(0, 0, w - 1, h - 1)
