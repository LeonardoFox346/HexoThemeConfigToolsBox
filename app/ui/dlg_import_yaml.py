"""导入 yml 配置页：挑一个现成的 yml，起个页面名，选个图标。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QFileDialog, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from .. import paths, theme
from . import icons

ICON_CHOICES = [
    "house", "pen", "server", "rocket", "palette", "id-card",
    "laptop", "link", "images", "lightbulb", "book-open", "film",
    "music", "gamepad", "code", "database", "cloud", "star",
    "heart", "folder-open", "file-lines", "chart-line", "globe", "camera",
    "mug-hot", "plane", "brain", "wand-magic-sparkles", "terminal", "compass",
]


class ImportYamlDialog(QDialog):
    """挑文件 → 起名 → 选图标。不新建、不改动原文件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导入 yml 配置页")
        self.setMinimumWidth(560)
        self._icon = ICON_CHOICES[0]
        self._build()
        self._update_preview()

    def _build(self):
        p = theme.c()
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(12)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("文件"))
        self.ed_file = QLineEdit()
        self.ed_file.setPlaceholderText("比如 <博客目录>/source/_data/xxx.yml")
        self.ed_file.textChanged.connect(self._update_preview)
        row.addWidget(self.ed_file, 1)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._pick_file)
        row.addWidget(browse)
        v.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(QLabel("名称"))
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("导航里显示的名字")
        self.ed_name.textChanged.connect(self._update_preview)
        row2.addWidget(self.ed_name, 1)
        v.addLayout(row2)

        v.addWidget(QLabel("图标"))
        grid = QGridLayout()
        grid.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for k, name in enumerate(ICON_CHOICES):
            b = QPushButton()
            b.setObjectName("IconPick")
            b.setCheckable(True)
            b.setFixedSize(40, 36)
            b.setIcon(icons.fa_icon(name, 18, p["ink"]))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(name)
            b.setProperty("icon_name", name)
            if k == 0:
                b.setChecked(True)
            self.group.addButton(b, k)
            grid.addWidget(b, k // 6, k % 6)
        self.group.idClicked.connect(self._pick)
        v.addLayout(grid)

        self.lbl_preview = QLabel("")
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.setStyleSheet(f"color: {p['ink2']};")
        v.addWidget(self.lbl_preview)

        tip = QLabel("导入只是把它加进导航，不改动文件本身；解析不出来时这一页直接显示原文。")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {p['ink2']};")
        v.addWidget(tip)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("导入")
        bb.button(QDialogButtonBox.Cancel).setText("取消")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        self.setStyleSheet(f"""
        QPushButton#IconPick {{ background: {p['field']}; border: 1px solid {p['line']};
                                border-radius: 7px; padding: 0px; }}
        QPushButton#IconPick:hover {{ border: 1px solid {p['accent']}; }}
        QPushButton#IconPick:checked {{ border: 2px solid {p['accent']};
                                        background: {p['accent_soft']}; }}
        """)

    def _pick_file(self):
        start = str(paths.DATA_DIR if paths.DATA_DIR.exists() else paths.BLOG)
        f, _ = QFileDialog.getOpenFileName(self, "选一个 yml", start,
                                           "YAML (*.yml *.yaml)")
        if f:
            self.ed_file.setText(f)
            if not self.ed_name.text().strip():
                self.ed_name.setText(Path(f).stem)

    def _pick(self, idx: int):
        self._icon = ICON_CHOICES[idx]

    def _update_preview(self):
        f = self.ed_file.text().strip()
        name = self.ed_name.text().strip() or (Path(f).stem if f else "")
        self.lbl_preview.setText(f"将导入：{f or '（还没选文件）'}　→　导航名「{name or '未命名'}」")
        if f and not self.ed_name.text().strip():
            self.ed_name.setText(Path(f).stem)

    def _accept(self):
        if not self.path().is_file():
            self.ed_file.setFocus()
            return
        if not self.ed_name.text().strip():
            self.ed_name.setFocus()
            return
        self.accept()

    # ── 给外面用 ──
    def path(self) -> Path:
        return Path(self.ed_file.text().strip()) if self.ed_file.text().strip() else Path()

    def page_name(self) -> str:
        return self.ed_name.text().strip()

    def page_icon(self) -> str:
        return self._icon
