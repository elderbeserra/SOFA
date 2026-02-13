"""Preferences / settings dialog for SOFA."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QWidget,
)

from .settings import (
    AnonymizationMode,
    get_anonymization_mode,
    get_blur_strength,
    get_box_padding,
    get_confidence_threshold,
    get_gpu_provider,
    get_output_scale,
    set_anonymization_mode,
    set_blur_strength,
    set_box_padding,
    set_confidence_threshold,
    set_gpu_provider,
    set_output_scale,
)


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Preferences')
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem('Black box', AnonymizationMode.BLACK_BOX)
        self.mode_combo.addItem('Blur', AnonymizationMode.BLUR)
        self.mode_combo.addItem('Pixelate', AnonymizationMode.PIXELATE)
        layout.addRow('Anonymization mode:', self.mode_combo)

        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(0, 200)
        self.padding_spin.setSuffix(' px')
        layout.addRow('Box padding:', self.padding_spin)

        self.blur_spin = QSpinBox()
        self.blur_spin.setRange(1, 99)
        self.blur_spin.setSingleStep(2)
        self.blur_spin.setToolTip('Gaussian blur kernel size (odd number)')
        layout.addRow('Blur strength:', self.blur_spin)

        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setDecimals(2)
        layout.addRow('Confidence threshold:', self.confidence_spin)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 1.0)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setDecimals(1)
        self.scale_spin.setSuffix(' (1.0 = full size)')
        layout.addRow('Output scale:', self.scale_spin)

        self.gpu_combo = QComboBox()
        self.gpu_combo.addItem('CPU (default)', '')
        self.gpu_combo.addItem('CUDA', 'CUDAExecutionProvider')
        self.gpu_combo.addItem('DirectML', 'DmlExecutionProvider')
        self.gpu_combo.addItem('CoreML', 'CoreMLExecutionProvider')
        self.gpu_combo.setToolTip('Requires corresponding ONNX Runtime build')
        layout.addRow('GPU provider:', self.gpu_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._restore_defaults)
        layout.addRow(buttons)

        self.setLayout(layout)

    def _load_values(self) -> None:
        mode = get_anonymization_mode()
        idx = self.mode_combo.findData(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.padding_spin.setValue(get_box_padding())
        self.blur_spin.setValue(get_blur_strength())
        self.confidence_spin.setValue(get_confidence_threshold())
        self.scale_spin.setValue(get_output_scale())
        provider = get_gpu_provider()
        idx = self.gpu_combo.findData(provider) if provider else 0
        if idx < 0:
            self.gpu_combo.addItem(provider or 'CPU', provider)
            idx = self.gpu_combo.count() - 1
        self.gpu_combo.setCurrentIndex(max(0, idx))

    def _save_values(self) -> None:
        set_anonymization_mode(self.mode_combo.currentData())
        set_box_padding(self.padding_spin.value())
        v = self.blur_spin.value()
        set_blur_strength(v + 1 if v % 2 == 0 else v)
        set_confidence_threshold(self.confidence_spin.value())
        set_output_scale(self.scale_spin.value())
        set_gpu_provider(self.gpu_combo.currentData() or '')

    def _save_and_accept(self) -> None:
        self._save_values()
        self.accept()

    def _restore_defaults(self) -> None:
        self.mode_combo.setCurrentIndex(0)
        self.padding_spin.setValue(10)
        self.blur_spin.setValue(31)
        self.confidence_spin.setValue(0.7)
        self.scale_spin.setValue(0.5)
        self.gpu_combo.setCurrentIndex(0)
