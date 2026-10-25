"""解析不出来的 yml：原文照读，不乱猜结构。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from .. import theme
from . import icons


class RawPage(QWidget):
    def __init__(self, title: str, path: Path, parent=None):
        super().__init__(parent)
        self.title = title
        self.path = Path(path)
        self.status_tip = "这一页没解析成结构，按原文显示"
        self._build()
        self.reload()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(8)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.lbl = QLabel(str(self.path))
        self.lbl.setObjectName("Dim")
        bar.addWidget(self.lbl, 1)
        b1 = QPushButton("重新读取")
        b1.setObjectName("ToolBtn")
        b1.clicked.connect(self.reload)
        b2 = QPushButton("用记事本打开")
        b2.setObjectName("ToolBtn")
        b2.clicked.connect(self._open_file)
        bar.addWidget(b1)
        bar.addWidget(b2)
        v.addLayout(bar)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(theme.mono_font(9))
        v.addWidget(self.text, 1)

        hint = QLabel("结构没解析出来，所以先按原文显示。想改内容用「用记事本打开」。")
        hint.setObjectName("Dim")
        v.addWidget(hint)

    def reload(self):
        try:
            self.text.setPlainText(self.path.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            self.text.setPlainText(f"读不出来：{e}")

    def _open_file(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))

    def apply_theme(self):
        self.text.setFont(theme.mono_font(9))
