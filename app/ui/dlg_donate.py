"""支持作者：显示内置赞赏码（或本地放的捐赠码）。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from .. import donate, theme


def _pic(pm: QPixmap, size: int = 220) -> QLabel:
    lab = QLabel()
    lab.setPixmap(pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    lab.setAlignment(Qt.AlignCenter)
    return lab


class DonateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("赞赏与支持")
        self.resize(440, 520)
        p = theme.c()
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(10)

        title = QLabel("感谢支持")
        title.setStyleSheet(
            f"font-size:18px; font-weight:700; color:{p['ink']}; background:transparent;")
        v.addWidget(title, 0, Qt.AlignHCenter)

        row = QHBoxLayout()
        row.setSpacing(16)
        builtin = donate.pixmap()
        if builtin is not None:
            box = QVBoxLayout()
            box.setSpacing(6)
            box.addWidget(_pic(builtin), 0, Qt.AlignHCenter)
            cap = QLabel("赞赏码")
            cap.setStyleSheet(f"color:{p['ink2']}; background:transparent;")
            box.addWidget(cap, 0, Qt.AlignHCenter)
            row.addLayout(box)
        else:
            for name, path in donate.images():
                pm = QPixmap(str(path))
                if pm.isNull():
                    continue
                box = QVBoxLayout()
                box.setSpacing(6)
                box.addWidget(_pic(pm), 0, Qt.AlignHCenter)
                cap = QLabel(name)
                cap.setStyleSheet(f"color:{p['ink2']}; background:transparent;")
                box.addWidget(cap, 0, Qt.AlignHCenter)
                row.addLayout(box)
        v.addLayout(row)

        tip = QLabel("赞赏完全自愿，不影响任何功能，也不代表购买服务。")
        tip.setWordWrap(True)
        tip.setAlignment(Qt.AlignHCenter)
        tip.setStyleSheet(f"color:{p['ink2']}; background:transparent;")
        v.addWidget(tip)
        if builtin is None and donate.images():
            warn = QLabel("内置赞赏码校验没通过，当前显示的是程序目录里的图片。")
            warn.setWordWrap(True)
            warn.setAlignment(Qt.AlignHCenter)
            warn.setStyleSheet("color:#c9a227; background:transparent;")
            v.addWidget(warn)
        v.addStretch(1)

        from . import badges
        v.addWidget(badges.gpl_badge(30), 0, Qt.AlignHCenter)
        note = QLabel("本程序以 GPL-3.0 开源")
        note.setAlignment(Qt.AlignHCenter)
        note.setStyleSheet(f"color:{p['ink2']}; background:transparent;")
        v.addWidget(note)

        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        v.addWidget(close, 0, Qt.AlignHCenter)
