import os
import sys
from functools import partial

from moviepy.editor import VideoFileClip
from PyQt5.QtCore import QDir, Qt, QUrl, pyqtSlot
from PyQt5.QtGui import QIcon, QImage, QKeySequence, QPixmap
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .bad_clips_slider import HlightSliderTipsWidget
from .bad_clips_table import BadClipsWidget
from .batch_dialog import BatchProcessDialog
from .proc_bar_dialog import ProcVideoDialog
from .project import load_project, save_project
from .settings_dialog import SettingsDialog
from .signals import SignalBus
from .utils import create_action, format_time, get_metadata_colors

TMP_VIDEO_PATH = os.path.join(QDir.homePath(), 'tmp_proc_video.mp4')
PROJECT_FILTER = 'SOFA project (*.sofa)'


class VideoWindow(QMainWindow):
    def __init__(self, app: QApplication, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.setWindowTitle('sofa')
        self.setWindowIcon(QIcon('src/static/img/tofu.png'))
        self.rate: float = 1
        self.isNewMark: bool = False
        self.openedFile: str | None = None
        self.initUI()
        self.set_default_shortcuts()
        self.shortcuts: dict = {}
        self.comm = SignalBus.instance()

    def initUI(self) -> None:
        videoWidget = self.create_player()
        self.errorLabel = QLabel()
        self.errorLabel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.create_menu_bar()
        self.wid = QWidget(self)
        self.setCentralWidget(self.wid)
        self.set_layout(videoWidget, self.wid)
        self.mediaPlayer.setVideoOutput(videoWidget)
        self.mediaPlayer.stateChanged.connect(self.mediaStateChanged)
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.error.connect(self.handleError)
        self._install_frame_shortcuts()

    def create_player(self) -> QVideoWidget:
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)

        videoWidget = QVideoWidget()
        self.clipsWidget = BadClipsWidget()
        self.create_control()

        self.playButton.clicked.connect(self.play)
        self.adv3Button.clicked.connect(partial(self.advance, 3))
        self.goBack3Button.clicked.connect(partial(self.back, 3))
        self.advanceButton.clicked.connect(partial(self.advance, 10))
        self.goBackButton.clicked.connect(partial(self.back, 10))
        self.frameBackButton.clicked.connect(
            lambda checked=False: self._back_one_frame()
        )
        self.frameFwdButton.clicked.connect(
            lambda checked=False: self._advance_one_frame()
        )
        self.positionSlider.sliderMoved.connect(self.setPosition)
        self.cutButton.clicked.connect(self.createMark)
        self.clipsWidget.thumbnail_requested.connect(self._on_thumbnail_requested)
        self.clipsWidget.marks_changed.connect(self._update_export_duration)

        return videoWidget

    def set_default_shortcuts(self) -> None:
        self.playButton.setShortcut(QKeySequence(Qt.Key_Space))
        self.advanceButton.setShortcut(QKeySequence(Qt.Key_Right))
        self.goBackButton.setShortcut(QKeySequence(Qt.Key_Left))
        self.cutButton.setShortcut(QKeySequence(Qt.Key_C))

    def create_control(self) -> None:
        self.playButton = _create_button(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.adv3Button = _create_button(
            self.style().standardIcon(QStyle.SP_ArrowRight)
        )
        self.advanceButton = _create_button(
            self.style().standardIcon(QStyle.SP_MediaSkipForward)
        )
        self.goBack3Button = _create_button(
            self.style().standardIcon(QStyle.SP_ArrowLeft)
        )
        self.goBackButton = _create_button(
            self.style().standardIcon(QStyle.SP_MediaSkipBackward)
        )
        self.frameBackButton = _create_button(
            self.style().standardIcon(QStyle.SP_MediaSeekBackward)
        )
        self.frameBackButton.setToolTip('Previous frame [')
        self.frameBackButton.setFocusPolicy(Qt.ClickFocus)
        self.frameFwdButton = _create_button(
            self.style().standardIcon(QStyle.SP_MediaSeekForward)
        )
        self.frameFwdButton.setToolTip('Next frame ]')
        self.frameFwdButton.setFocusPolicy(Qt.ClickFocus)
        self.cutButton = _create_button(
            self.style().standardIcon(QStyle.SP_MessageBoxCritical)
        )
        self.timeBox = QLabel(format_time(0), self)
        self.timeBox.setAlignment(Qt.AlignCenter)
        self.rateBox = QLabel(str(self.rate) + 'x', self)
        self.rateBox.setAlignment(Qt.AlignCenter)
        self.exportDurationLabel = QLabel('Export duration: —', self)
        self.exportDurationLabel.setAlignment(Qt.AlignCenter)
        self.hlightSliderTips = HlightSliderTipsWidget()
        self.positionSlider = QSlider(Qt.Horizontal)
        self.positionSlider.setRange(0, 0)

    def create_menu_bar(self) -> None:
        openAction = create_action(
            'open.png', '&Open', 'Ctrl+O', 'Open video', self.openFile, self
        )
        saveAction = create_action(
            'save.png',
            '&Save Clips',
            'Ctrl+S',
            'Save anonimized clips',
            self.saveClips,
            self,
        )
        saveProjectAction = create_action(
            '', 'Save &Project...', '',
            'Save project (video path and clip marks)', self._save_project, self,
        )
        openProjectAction = create_action(
            '', 'Open Proj&ect...', '',
            'Open project file', self._open_project, self,
        )
        exitAction = create_action(
            'exit.png', '&Exit', 'Ctrl+Q', 'Exit', self.exitCall, self
        )
        undoAction = create_action(
            '', '&Undo', 'Ctrl+Z', 'Undo last clip mark', self._undo_mark, self
        )
        redoAction = create_action(
            '', '&Redo', 'Ctrl+Shift+Z', 'Redo clip mark', self._redo_mark, self
        )
        settingsAction = create_action(
            '', '&Preferences...', '',
            'Application settings', self._open_settings, self,
        )
        batchAction = create_action(
            '', '&Batch process...', '',
            'Process multiple videos', self._open_batch_dialog, self,
        )

        menuBar = self.menuBar()
        fileMenu = menuBar.addMenu('&File')
        fileMenu.addAction(openAction)
        fileMenu.addAction(openProjectAction)
        fileMenu.addAction(saveAction)
        fileMenu.addAction(saveProjectAction)
        fileMenu.addAction(batchAction)
        fileMenu.addAction(exitAction)
        editMenu = menuBar.addMenu('&Edit')
        editMenu.addAction(undoAction)
        editMenu.addAction(redoAction)
        editMenu.addAction(settingsAction)

    def set_layout(self, videoWidget: QVideoWidget, wid: QWidget) -> None:
        labellingLayout = QVBoxLayout()
        labellingLayout.addWidget(self.clipsWidget)

        controlLayout = self.make_control_layout()

        videoAreaLayout = QVBoxLayout()
        videoWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        videoAreaLayout.addWidget(videoWidget)
        videoAreaLayout.addLayout(controlLayout)
        videoAreaLayout.addWidget(self.errorLabel)

        layout = QHBoxLayout()
        layout.addLayout(videoAreaLayout, 4)
        layout.addLayout(labellingLayout)

        wid.setLayout(layout)

    def make_control_layout(self) -> QVBoxLayout:
        buttonsLayout = QHBoxLayout()
        buttonsLayout.setContentsMargins(0, 0, 0, 0)
        buttonsLayout.addWidget(self.timeBox)
        buttonsLayout.addWidget(self.goBackButton)
        buttonsLayout.addWidget(self.goBack3Button)
        buttonsLayout.addWidget(self.frameBackButton)
        buttonsLayout.addWidget(self.playButton)
        buttonsLayout.addWidget(self.frameFwdButton)
        buttonsLayout.addWidget(self.adv3Button)
        buttonsLayout.addWidget(self.advanceButton)
        buttonsLayout.addWidget(self.rateBox)
        cutLayout = QHBoxLayout()
        cutLayout.setContentsMargins(0, 0, 0, 0)
        cutLayout.addSpacerItem(
            QSpacerItem(200, 5, QSizePolicy.Minimum, QSizePolicy.Minimum)
        )
        cutLayout.addWidget(self.cutButton)
        cutLayout.addSpacerItem(
            QSpacerItem(200, 5, QSizePolicy.Minimum, QSizePolicy.Minimum)
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.positionSlider)
        layout.addWidget(self.hlightSliderTips)
        layout.addLayout(buttonsLayout)
        layout.addWidget(self.exportDurationLabel)
        layout.addLayout(cutLayout)
        return layout

    def openFile(self) -> None:
        self.rawFileName, _ = QFileDialog.getOpenFileName(
            self, 'Open video', QDir.homePath()
        )
        if self.rawFileName != '':
            should_process = QMessageBox.question(
                self.wid,
                'Open video',
                'Do you want to pre process the video?',
                QMessageBox.Yes | QMessageBox.No,
            )
            if should_process == QMessageBox.Yes:
                self.fileName = TMP_VIDEO_PATH
                ProcVideoDialog(self.rawFileName, self.fileName, self)
                self.comm.videoProcessed.connect(self.openMedia)
            else:
                self.fileName = self.rawFileName
                self.processMetaData()
                self.openMedia()

    def processMetaData(self) -> None:
        """
        Get array indicating "suspicious" frames
        """
        # open metadata file
        self.metaDataFile = self.fileName.rsplit('.', 1)[0] + '.csv'
        # get only the array with "colors" (==0: green; !=0: red)
        self.colorsArray = get_metadata_colors(self.metaDataFile)
        self.hlightSliderTips.setColorsArray(self.colorsArray, useYellow=False)

    @pyqtSlot()
    def openMedia(self) -> None:
        self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(self.fileName)))
        self.openedFile = os.path.basename(self.fileName)
        self.setWindowTitle('sofa - ' + self.openedFile)
        self.clipsWidget.set_video_path(self.fileName)
        self.playButton.setEnabled(True)
        self.advanceButton.setEnabled(True)
        self.adv3Button.setEnabled(True)
        self.goBackButton.setEnabled(True)
        self.goBack3Button.setEnabled(True)
        self.cutButton.setEnabled(True)
        self.rate = 1
        self._update_export_duration()
        self.frameBackButton.setEnabled(True)
        self.frameFwdButton.setEnabled(True)

    def exitCall(self) -> None:
        if self.openedFile is not None and self.fileName == TMP_VIDEO_PATH:
            if os.path.isfile(self.fileName):
                os.remove(self.fileName)
        sys.exit(self.app.exec())

    def play(self) -> None:
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()

    def slow(self) -> None:
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.rate -= 0.5
            # TODO: Workaround pt 1
            # https://forum.qt.io/topic/88490/change-playback-rate-at-...
            # ...runtime-problem-with-position-qmediaplayer/8
            currentPos = self.mediaPlayer.position()
            # TODO: Workaround pt 1
            self.mediaPlayer.setPlaybackRate(self.rate)
            # TODO: Workaround pt 2
            self.mediaPlayer.setPosition(currentPos)
            # TODO: Workaround pt 2: end
            self.rateBox.setText(str(self.rate) + 'x')

    def speed(self) -> None:
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.rate += 0.5
            # TODO: Workaround pt 1
            # https://forum.qt.io/topic/88490/change-playback-rate-at-...
            # ...runtime-problem-with-position-qmediaplayer/8
            currentPos = self.mediaPlayer.position()
            # TODO: Workaround pt 1
            self.mediaPlayer.setPlaybackRate(self.rate)
            # TODO: Workaround pt 2
            self.mediaPlayer.setPosition(currentPos)
            # TODO: Workaround pt 2: end
            self.rateBox.setText(str(self.rate) + 'x')

    def advance(self, t: int = 10) -> None:
        currentPos = self.mediaPlayer.position()
        nextPos = currentPos + t * 1000
        self.setPosition(nextPos)

    def back(self, t: int = 10) -> None:
        currentPos = self.mediaPlayer.position()
        nextPos = max(currentPos - t * 1000, 0)
        self.setPosition(nextPos)

    def _step_one_frame(self, forward: bool) -> None:
        dur_ms = self.mediaPlayer.duration()
        if dur_ms <= 0:
            return
        was_playing = self.mediaPlayer.state() == QMediaPlayer.PlayingState
        if was_playing:
            self.mediaPlayer.pause()
        frame_ms = max(1, int(1000 / 30))
        pos = self.mediaPlayer.position()
        if forward:
            new_pos = min(pos + frame_ms, dur_ms)
        else:
            new_pos = max(0, pos - frame_ms)
        self.mediaPlayer.setPosition(new_pos)
        if was_playing:
            self.mediaPlayer.play()

    @pyqtSlot()
    def _advance_one_frame(self) -> None:
        self._step_one_frame(forward=True)

    @pyqtSlot()
    def _back_one_frame(self) -> None:
        self._step_one_frame(forward=False)

    def _install_frame_shortcuts(self) -> None:
        for shortcut in getattr(self, '_frame_shortcuts', []):
            shortcut.deleteLater()
        back_shortcut = QShortcut(QKeySequence('['), self)
        back_shortcut.setContext(Qt.ApplicationShortcut)
        back_shortcut.activated.connect(self._back_one_frame)
        fwd_shortcut = QShortcut(QKeySequence(']'), self)
        fwd_shortcut.setContext(Qt.ApplicationShortcut)
        fwd_shortcut.activated.connect(self._advance_one_frame)
        speed_up_shortcut = QShortcut(QKeySequence(Qt.Key_Up), self)
        speed_up_shortcut.setContext(Qt.ApplicationShortcut)
        speed_up_shortcut.activated.connect(self.speed)
        speed_down_shortcut = QShortcut(QKeySequence(Qt.Key_Down), self)
        speed_down_shortcut.setContext(Qt.ApplicationShortcut)
        speed_down_shortcut.activated.connect(self.slow)
        self._frame_shortcuts = [
            back_shortcut,
            fwd_shortcut,
            speed_up_shortcut,
            speed_down_shortcut,
        ]

    @pyqtSlot(int, float)
    def _on_thumbnail_requested(self, row: int, time_sec: float) -> None:
        if not getattr(self, 'fileName', None) or not os.path.isfile(self.fileName):
            return
        try:
            clip = VideoFileClip(self.fileName)
            frame = clip.get_frame(time_sec).copy()
            clip.close()
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.clipsWidget.set_thumbnail(row, QPixmap.fromImage(qimg.copy()))
        except Exception:
            self.clipsWidget.set_thumbnail(row, None)

    @pyqtSlot()
    def _update_export_duration(self) -> None:
        marks = self.clipsWidget.get_marks()
        if not marks:
            self.exportDurationLabel.setText('Export duration: —')
            return
        total_sec = sum(float(m[2]) for m in marks if len(m) >= 3)
        self.exportDurationLabel.setText(f'Export duration: {format_time(int(total_sec))}')

    @pyqtSlot()
    def _undo_mark(self) -> None:
        if self.clipsWidget.undo():
            self.isNewMark = True

    @pyqtSlot()
    def _redo_mark(self) -> None:
        self.clipsWidget.redo()

    @pyqtSlot()
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        dlg.exec_()

    @pyqtSlot()
    def _open_batch_dialog(self) -> None:
        dlg = BatchProcessDialog(self)
        dlg.exec_()

    @pyqtSlot()
    def _save_project(self) -> None:
        if not getattr(self, 'openedFile', None):
            QMessageBox.information(
                self.wid,
                'Save Project',
                'Open a video before saving a project.',
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save Project', QDir.homePath(), PROJECT_FILTER
        )
        if path:
            if not path.endswith('.sofa'):
                path = path + '.sofa'
            try:
                save_project(
                    path,
                    self.rawFileName,
                    self.fileName,
                    self.clipsWidget.get_marks(),
                )
                QMessageBox.information(
                    self.wid, 'Save Project', 'Project saved successfully.'
                )
            except Exception as e:
                QMessageBox.warning(
                    self.wid, 'Error', f'Could not save project: {e}'
                )

    @pyqtSlot()
    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open Project', QDir.homePath(), PROJECT_FILTER
        )
        if not path:
            return
        try:
            data = load_project(path)
        except Exception as e:
            QMessageBox.warning(
                self.wid, 'Error', f'Could not open project: {e}'
            )
            return
        raw = data.get('raw_file_name', '')
        file_path = data.get('file_name', '')
        marks = data.get('marks', [])
        if not file_path or not os.path.isfile(file_path):
            QMessageBox.warning(
                self.wid,
                'Open Project',
                'Video file not found. It may have been moved or deleted.',
            )
            return
        self.rawFileName = raw or file_path
        self.fileName = file_path
        self.processMetaData()
        self.openMedia()
        self.clipsWidget.set_marks(marks)
        self._update_export_duration()

    def mediaStateChanged(self, state: int) -> None:
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def positionChanged(self, position: int) -> None:
        self.positionSlider.setValue(position)
        self.hlightSliderTips.setValue(position)
        self.timeBox.setText(format_time(int(position / 1000)))

    def durationChanged(self, duration: int) -> None:
        self.positionSlider.setRange(0, duration)
        self.hlightSliderTips.setRange(duration)
        self._update_export_duration()

    def setPosition(self, position: int) -> None:
        self.mediaPlayer.setPosition(position)

    def handleError(self) -> None:
        self.playButton.setEnabled(False)
        self.advanceButton.setEnabled(False)
        self.goBackButton.setEnabled(False)
        self.frameBackButton.setEnabled(False)
        self.frameFwdButton.setEnabled(False)
        self.errorLabel.setText('Error: ' + self.mediaPlayer.errorString())

    def saveClips(self) -> None:
        prefix = os.path.splitext(os.path.basename(self.rawFileName))[0] + '_clip_'
        dirPath = QFileDialog.getExistingDirectory(self, 'Select Dir')
        if dirPath != '':
            try:
                self.errorLabel.setText('Saving clips... please wait')
                video = VideoFileClip(self.fileName)
                marks = self.clipsWidget.get_marks()
                for i, m in enumerate(marks):
                    begin_time = float(m[0])
                    end_time = float(m[1])
                    if begin_time >= end_time:
                        continue
                    out_path = os.path.join(dirPath, prefix + str(i) + '.mp4')
                    clip = video.subclip(begin_time, end_time)
                    clip.write_videofile(out_path)
                self.errorLabel.setText('Clips saved at ' + dirPath)
                QMessageBox.information(self.wid, 'Success', 'Clips successfully saved')
            except Exception:
                self.errorLabel.setText('Error: Could not save file.')
                QMessageBox.warning(
                    self.wid,
                    'Error',
                    'Could not save file. Check permissions',
                )

    @pyqtSlot()
    def createMark(self) -> None:
        state = self.mediaPlayer.state()
        if state == QMediaPlayer.PlayingState or state == QMediaPlayer.PausedState:
            self.clipsWidget.new_mark(
                self.mediaPlayer.position() / 1000, self.isNewMark
            )
            self.isNewMark = not self.isNewMark


def _create_button(icon: QIcon) -> QPushButton:
    button = QPushButton()
    button.setIcon(icon)
    button.setEnabled(False)
    return button
