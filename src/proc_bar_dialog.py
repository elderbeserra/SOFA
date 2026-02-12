import os
from threading import Thread

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QDialog, QProgressBar, QPushButton, QVBoxLayout, QWidget

from .face_recog import UltraLightFaceRecog
from .signals import SignalBus


class ProcVideoDialog(QDialog):
    def __init__(
        self,
        raw_file_name: str,
        file_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.comm = SignalBus.instance()
        self.comm.updProgress.connect(self.updProgress)
        self.fileName = file_name
        self.faceRecog = UltraLightFaceRecog()
        self.procThread = Thread(
            target=self.faceRecog.blur_faces,
            args=(raw_file_name, self.fileName),
        )
        self.procThread.start()
        self.done: bool = False
        self.initUI()

    def initUI(self) -> None:
        self.setWindowTitle('Processing video')
        self.progress = QProgressBar(self)
        self.progress.setMaximum(100)
        self.cancelButton = QPushButton('cancel', self)
        self.cancelButton.clicked.connect(self.close)
        layout = QVBoxLayout()
        layout.addWidget(self.progress)
        layout.addWidget(self.cancelButton)
        self.setLayout(layout)
        self.show()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.done:
            self.faceRecog.stop()
            self.procThread.join()
            if os.path.isfile(self.fileName):
                os.remove(self.fileName)

    @pyqtSlot(float)
    def updProgress(self, prog: float) -> None:
        self.progress.setValue(int(prog))
        if prog == 100.0:
            self.done = True
            self.close()
