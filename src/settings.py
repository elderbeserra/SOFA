"""Application settings with optional Qt persistence."""

from enum import Enum
from typing import Any

# Defaults when running without Qt (e.g. CLI)
_ANONYMIZATION_MODE_KEY = 'anonymization_mode'
_BOX_PADDING_KEY = 'box_padding'
_BLUR_STRENGTH_KEY = 'blur_strength'
_CONFIDENCE_THRESHOLD_KEY = 'confidence_threshold'
_OUTPUT_SCALE_KEY = 'output_scale'
_GPU_PROVIDER_KEY = 'gpu_provider'

DEFAULT_BOX_PADDING = 10
DEFAULT_BLUR_STRENGTH = 31  # odd for GaussianBlur
DEFAULT_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_OUTPUT_SCALE = 0.5  # 50% resolution
DEFAULT_GPU_PROVIDER = ''  # empty = CPU


class AnonymizationMode(str, Enum):
    """How to anonymize detected face regions."""

    BLACK_BOX = 'black_box'
    BLUR = 'blur'
    PIXELATE = 'pixelate'


_defaults: dict[str, Any] = {
    _ANONYMIZATION_MODE_KEY: AnonymizationMode.BLACK_BOX.value,
    _BOX_PADDING_KEY: DEFAULT_BOX_PADDING,
    _BLUR_STRENGTH_KEY: DEFAULT_BLUR_STRENGTH,
    _CONFIDENCE_THRESHOLD_KEY: DEFAULT_CONFIDENCE_THRESHOLD,
    _OUTPUT_SCALE_KEY: DEFAULT_OUTPUT_SCALE,
    _GPU_PROVIDER_KEY: DEFAULT_GPU_PROVIDER,
}


def _qsettings():
    """Return QSettings instance if Qt is available, else None."""
    try:
        from PyQt5.QtCore import QSettings
        return QSettings('SOFA', 'sofa')
    except Exception:
        return None


def get(key: str, default: Any = None) -> Any:
    """Get a setting value; use default or _defaults if not persisted."""
    qs = _qsettings()
    if qs is not None:
        qs.beginGroup('anonymization')
        val = qs.value(key, _defaults.get(key, default))
        qs.endGroup()
        if val is not None:
            return val
    return _defaults.get(key, default)


def set_value(key: str, value: Any) -> None:
    """Persist a setting (no-op if Qt not available)."""
    qs = _qsettings()
    if qs is not None:
        qs.beginGroup('anonymization')
        qs.setValue(key, value)
        qs.endGroup()


def get_anonymization_mode() -> AnonymizationMode:
    raw = get(_ANONYMIZATION_MODE_KEY)
    if isinstance(raw, AnonymizationMode):
        return raw
    try:
        return AnonymizationMode(str(raw))
    except ValueError:
        return AnonymizationMode.BLACK_BOX


def set_anonymization_mode(mode: AnonymizationMode) -> None:
    set_value(_ANONYMIZATION_MODE_KEY, mode.value)


def get_box_padding() -> int:
    v = get(_BOX_PADDING_KEY)
    return int(v) if v is not None else DEFAULT_BOX_PADDING


def set_box_padding(pixels: int) -> None:
    set_value(_BOX_PADDING_KEY, max(0, int(pixels)))


def get_blur_strength() -> int:
    v = get(_BLUR_STRENGTH_KEY)
    return int(v) if v is not None else DEFAULT_BLUR_STRENGTH


def set_blur_strength(kernel_size: int) -> None:
    k = max(1, int(kernel_size))
    if k % 2 == 0:
        k += 1
    set_value(_BLUR_STRENGTH_KEY, k)


def get_confidence_threshold() -> float:
    v = get(_CONFIDENCE_THRESHOLD_KEY)
    return float(v) if v is not None else DEFAULT_CONFIDENCE_THRESHOLD


def set_confidence_threshold(threshold: float) -> None:
    set_value(_CONFIDENCE_THRESHOLD_KEY, max(0.0, min(1.0, float(threshold))))


def get_output_scale() -> float:
    v = get(_OUTPUT_SCALE_KEY)
    return float(v) if v is not None else DEFAULT_OUTPUT_SCALE


def set_output_scale(scale: float) -> None:
    set_value(_OUTPUT_SCALE_KEY, max(0.1, min(1.0, float(scale))))


def get_gpu_provider() -> str:
    v = get(_GPU_PROVIDER_KEY)
    return str(v) if v is not None else DEFAULT_GPU_PROVIDER


def set_gpu_provider(provider: str) -> None:
    set_value(_GPU_PROVIDER_KEY, str(provider))
