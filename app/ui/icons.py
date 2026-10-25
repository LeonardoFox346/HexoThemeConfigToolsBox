"""把 Font Awesome 字形渲染成 QIcon —— 菜单项、状态栏按钮用。"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap

from .. import fa, theme

from ..paths import APP_DIR

_LOGO_SRC = APP_DIR / "icon-source.png"
_logo_cache: dict = {}


def fox_logo(size: int = 64) -> QPixmap:
    """程序图标：从 app.ico 取（不读取、不分发原稿）。"""
    key = size
    if key in _logo_cache:
        return _logo_cache[key]
    from ..paths import APP_DIR
    ico = APP_DIR / "app.ico"
    if ico.exists():
        pm = QIcon(str(ico)).pixmap(size, size)
        if not pm.isNull():
            _logo_cache[key] = pm
            return pm
    return QPixmap()


def fa_pixmap(name: str, size: int = 16, color: str | None = None) -> QPixmap:
    """渲染一个图标。

    画布按 1.6 倍渲染、显示时由 Qt 缩放到目标尺寸 ——
    直接用目标尺寸画的话，FA 字形（实际占约 1em）会溢出画布被裁掉，
    表现就是图标只剩半截或变形。
    """
    p = theme.c()
    scale = 3
    px = max(24, int(round(size * scale)))
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    g = QPainter(pm)
    g.setRenderHint(QPainter.Antialiasing, True)
    g.setRenderHint(QPainter.TextAntialiasing, True)
    g.setFont(theme.icon_font(px * 0.62))
    g.setPen(QColor(color or p["ink2"]))
    g.drawText(pm.rect(), Qt.AlignCenter, fa.get(name))
    g.end()
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def fa_icon(name: str, size: int = 16, color: str | None = None,
            active: bool = False) -> QIcon:
    """生成图标。active=True 用强调色（表示开着的状态）。"""
    if active:
        color = theme.c()["accent"]
    return QIcon(fa_pixmap(name, size, color))


def refresh_icon(button, name: str, size: int = 14):
    """状态变了之后重画按钮图标（颜色跟着亮/暗）。"""
    try:
        button.setIcon(fa_icon(name, size, active=button.isChecked()))
    except RuntimeError:
        pass
