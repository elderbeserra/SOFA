"""Batch face anonymization dialog."""

import os
from typing import List

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .face_recog import UltraLightFaceRecog
from .signals import SignalBus


class BatchWorker(QObject):
    """Runs face blurring on multiple videos in sequence (run in a QThread)."""

    batchFinished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.files: List[str] = []
        self.output_dir = ''
        self.current_file_index = 0
        self.total_files = 0
        self._cancelled = False
        self._face_recog: UltraLightFaceRecog | None = None
        self.comm = SignalBus.instance()

    def cancel(self) -> None:
        self._cancelled = True
        if self._face_recog is not None:
            self._face_recog.stop()

    @pyqtSlot()
    def run(self) -> None:
        self.total_files = max(1, len(self.files))
        for i, inp in enumerate(self.files):
            if self._cancelled:
                break
            self.current_file_index = i
            self._face_recog = UltraLightFaceRecog()
            base = os.path.splitext(os.path.basename(inp))[0]
            out = os.path.join(self.output_dir, base + '_anon.mp4')
            try:
                self._face_recog.blur_faces(inp, out)
            except Exception:
                pass
            finally:
                self._face_recog = None
        self.comm.updProgress.emit(100.0)
        self.batchFinished.emit()


class BatchProcessDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Batch process')
        self._worker: BatchWorker | None = None
        self._thread: QThread | None = None
        self._comm = SignalBus.instance()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel('Videos to process:'))
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton('Add files...')
        add_btn.clicked.connect(self._add_files)
        remove_btn = QPushButton('Remove selected')
        remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        layout.addLayout(btn_layout)

        layout.addWidget(QLabel('Output directory:'))
        out_layout = QHBoxLayout()
        self.output_label = QLabel('(not set)')
        self.output_label.setStyleSheet('color: gray;')
        out_layout.addWidget(self.output_label)
        browse_btn = QPushButton('Browse...')
        browse_btn.clicked.connect(self._choose_output_dir)
        out_layout.addWidget(browse_btn)
        layout.addLayout(out_layout)

        self.current_file_label = QLabel('')
        layout.addWidget(self.current_file_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        run_btn = QPushButton('Run')
        run_btn.clicked.connect(self._run_batch)
        self.cancel_btn = QPushButton('Cancel')
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_batch)
        btn_row.addWidget(run_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self._output_dir = ''

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, 'Select videos', '', 'Videos (*.mp4 *.avi *.mov *.mkv);;All (*)'
        )
        for p in paths:
            self.list_widget.addItem(QListWidgetItem(p))

    def _remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def _choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, 'Output directory')
        if path:
            self._output_dir = path
            self.output_label.setText(path)
            self.output_label.setStyleSheet('')

    @pyqtSlot(float)
    def _on_progress(self, progress: float) -> None:
        if self._worker is None:
            return
        overall = (self._worker.current_file_index + progress / 100.0) / max(
            1, self._worker.total_files
        ) * 100.0
        self.progress_bar.setValue(int(overall))
        self.current_file_label.setText(
            f'Processing {self._worker.current_file_index + 1} of {self._worker.total_files}'
        )

    def _run_batch(self) -> None:
        count = self.list_widget.count()
        if count == 0:
            QMessageBox.warning(
                self, 'Batch process', 'Add at least one video.'
            )
            return
        if not self._output_dir or not os.path.isdir(self._output_dir):
            QMessageBox.warning(
                self, 'Batch process', 'Choose an output directory.'
            )
            return
        files = [
            self.list_widget.item(i).text()
            for i in range(count)
            if os.path.isfile(self.list_widget.item(i).text())
        ]
        if not files:
            QMessageBox.warning(
                self, 'Batch process', 'No valid video paths.'
            )
            return
        self.progress_bar.setValue(0)
        self.current_file_label.setText('')
        self.cancel_btn.setEnabled(True)
        self._worker = BatchWorker()
        self._worker.files = files
        self._worker.output_dir = self._output_dir
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.batchFinished.connect(self._on_batch_finished)
        self._worker.batchFinished.connect(self._thread.quit)
        self._comm.updProgress.connect(self._on_progress)
        self._thread.start()

    def _cancel_batch(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
        self.cancel_btn.setEnabled(False)

    @pyqtSlot()
    def _on_batch_finished(self) -> None:
        self._comm.updProgress.disconnect(self._on_progress)
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        self._worker = None
        self._thread = None
        self.cancel_btn.setEnabled(False)
        self.current_file_label.setText('Done.')
        QMessageBox.information(
            self, 'Batch process', 'Batch processing finished.'
        )
