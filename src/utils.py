from collections.abc import Callable
from typing import Any

import pandas as pd
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QWidget


def create_action(
    icon: str,
    action: str,
    shortcut: str,
    tip: str,
    conn: Callable[..., Any],
    parent: QWidget,
) -> QAction:
    new_action = QAction(QIcon(icon), action, parent)
    new_action.setShortcut(shortcut)
    new_action.setStatusTip(tip)
    new_action.triggered.connect(conn)
    return new_action


def format_time(sec: int) -> str:
    seconds = int(sec % 60)
    total_minutes = sec // 60
    minutes = int(total_minutes % 60)
    hours = int(total_minutes // 60)
    formatted = [str(t).zfill(2) for t in (hours, minutes, seconds)]
    return ':'.join(formatted)


def get_metadata_colors(filename: str) -> pd.Series | list:
    try:
        df = pd.read_csv(filename).sort_values(by='frame_num', ascending=True)
        return df['diff']
    except Exception:
        return []
