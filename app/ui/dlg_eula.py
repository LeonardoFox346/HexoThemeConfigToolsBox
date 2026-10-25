"""许可协议：只读查看。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout

from .. import eula


class EulaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("软件使用许可协议")
        self.resize(720, 640)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)
        br = QTextBrowser()
        br.setOpenExternalLinks(True)
        br.setPlainText(eula.EULA_TEXT)
        v.addWidget(br, 1)
        row = QHBoxLayout()
        ver = QPushButton("查看 GPL-3.0 中文说明")
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from .. import licenses
        ver.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(licenses.GPL_ZH_URL)))
        row.addWidget(ver)
        row.addStretch(1)
        b = QPushButton("关闭")
        b.clicked.connect(self.accept)
        row.addWidget(b)
        v.addLayout(row)
