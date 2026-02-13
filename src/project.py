"""SOFA project save/load (.sofa JSON format)."""

import json
import os
from typing import Any


PROJECT_VERSION = 1


def save_project(path: str, raw_file_name: str, file_name: str, marks: list[list[str]]) -> None:
    """Write project to a .sofa file."""
    raw_abs = os.path.abspath(raw_file_name) if raw_file_name else ''
    file_abs = os.path.abspath(file_name) if file_name else ''
    data: dict[str, Any] = {
        'version': PROJECT_VERSION,
        'raw_file_name': raw_abs,
        'file_name': file_abs,
        'marks': list(marks),
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def load_project(path: str) -> dict[str, Any]:
    """Read project from a .sofa file. Returns dict with raw_file_name, file_name, marks."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    version = data.get('version', 0)
    if version > PROJECT_VERSION:
        raise ValueError(f'Unsupported project version {version}')
    raw = data.get('raw_file_name', '')
    file_name = data.get('file_name', raw)
    open_path = file_name if (file_name and os.path.isfile(file_name)) else raw
    if not open_path or not os.path.isfile(open_path):
        open_path = raw
    marks = data.get('marks', [])
    if not isinstance(marks, list):
        marks = []
    marks = [m for m in marks if isinstance(m, list) and len(m) >= 3]
    return {
        'raw_file_name': raw,
        'file_name': open_path,
        'marks': marks,
    }
