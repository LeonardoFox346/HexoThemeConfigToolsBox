"""开源项目徽标：圆角底色 + 品牌图标（FA 没有的用首字母）。"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

from .. import fa, theme


def badge(icon: str, color: str, size: int = 44, fallback: str = "?") -> QPixmap:
    px = size * 3
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    q = QPainter(pm)
    q.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    bg = QColor(c)
    bg.setAlphaF(0.22)
    edge = QColor(c)
    edge.setAlphaF(0.55)
    q.setBrush(bg)
    q.setPen(edge)
    q.drawRoundedRect(QRect(3, 3, px - 6, px - 6), px * 0.22, px * 0.22)

    glyph = fa.get(icon) if icon else ""
    f = theme.icon_font(size * 0.5)
    f.setPixelSize(max(10, int(px * 0.56)))
    q.setFont(f)
    q.setPen(c)
    if glyph:
        q.drawText(QRect(0, 0, px, px), Qt.AlignCenter, glyph)
    else:
        gf = theme.ui_font(size * 0.5, bold=True)
        gf.setPixelSize(max(10, int(px * 0.46)))
        q.setFont(gf)
        q.drawText(QRect(0, 0, px, px), Qt.AlignCenter, fallback[:1].upper())
    q.end()
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

def gpl_badge(height: int = 28):
    """GPLv3 徽标，点一下打开中文说明。"""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QLabel
    from .. import licenses
    lab = QLabel()
    lab.setPixmap(licenses.badge_pixmap(height))
    lab.setCursor(Qt.PointingHandCursor)
    lab.setToolTip("GPL-3.0-or-later　·　点一下看中文说明")
    lab.mousePressEvent = lambda _e: QDesktopServices.openUrl(QUrl(licenses.GPL_ZH_URL))
    return lab
