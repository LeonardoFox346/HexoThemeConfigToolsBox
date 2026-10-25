"""看原文：只读弹窗，给导入的 yml 用。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from .. import theme


class RawViewDialog(QDialog):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.setWindowTitle(f"原文 — {self.path.name}")
        self.resize(860, 620)
        self._build()
        self.reload()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)

        bar = QHBoxLayout()
        lab = QLabel(str(self.path))
        lab.setObjectName("Dim")
        bar.addWidget(lab, 1)
        b1 = QPushButton("重新读取")
        b1.setObjectName("ToolBtn")
        b1.clicked.connect(self.reload)
        b2 = QPushButton("关闭")
        b2.clicked.connect(self.accept)
        bar.addWidget(b1)
        bar.addWidget(b2)
        v.addLayout(bar)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(theme.mono_font(9))
        v.addWidget(self.text, 1)

        tip = QLabel("只读。要改内容请回表单里改，或者用外部编辑器打开文件。")
        tip.setObjectName("Dim")
        v.addWidget(tip)

    def reload(self):
        try:
            self.text.setPlainText(self.path.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            self.text.setPlainText(f"读不出来：{e}")
