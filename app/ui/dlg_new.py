"""新建文章对话框：一次把所有 Front Matter 字段都摊开。

每个输入框都带占位提示（格式示例），空着也能建 —— 建完还能在「文章信息」面板里改。
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout,
)

from ..paths import CATEGORIES
from . import anim

# 版权类型：主题里实际用到的就是 type1 / type2，但这里把 1–5 都列出来，
# 免得记不清编号时没得选。选「关闭」就不写 copyright 字段。
CRIGHT_TYPES = ["type1", "type2", "type3", "type4", "type5", "关闭"]


class NewArticleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建文章")
        self.setMinimumWidth(620)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.ed_title = QLineEdit()
        self.ed_title.setPlaceholderText("写一个能当标题的句子")
        form.addRow("标题", self.ed_title)

        self.ed_date = QLineEdit()
        self.ed_date.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.ed_date.setPlaceholderText("yyyy-mm-dd HH:MM:SS")
        form.addRow("日期", self.ed_date)

        self.cb_cat = QComboBox()
        self.cb_cat.addItems(CATEGORIES)
        form.addRow("分类", self.cb_cat)

        self.ed_tags = QLineEdit()
        self.ed_tags.setPlaceholderText("用逗号或顿号分隔，例如：安全、运维（可留空）")
        form.addRow("标签", self.ed_tags)

        self.ed_cover = QLineEdit()
        self.ed_cover.setPlaceholderText("https://… 图片地址（可留空，首页会没有封面图）")
        form.addRow("封面", self.ed_cover)

        self.ed_desc = QLineEdit()
        self.ed_desc.setPlaceholderText("一两句话，会显示在首页卡片上（可留空）")
        form.addRow("简介", self.ed_desc)

        self.cb_cright = QComboBox()
        self.cb_cright.addItems(CRIGHT_TYPES)
        self.cb_cright.setToolTip(
            "写进 Front Matter 的 copyright.type。\n"
            "主题实际只区分 type1 和 type2，其余编号会按默认样式处理。\n"
            "选「关闭」就不写这个字段。")
        form.addRow("版权", self.cb_cright)

        self.ed_author = QLineEdit()
        self.ed_author.setPlaceholderText("留空用站点默认作者")
        form.addRow("作者", self.ed_author)

        root.addLayout(form)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("创建")
        bb.button(QDialogButtonBox.Cancel).setText("取消")
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self.ed_title.setFocus()

    def _on_ok(self):
        if not self.ed_title.text().strip():
            self.ed_title.setFocus()
            self.ed_title.setPlaceholderText("标题总得有一个吧")
            anim.flash_error(self.ed_title)
            anim.shake(self)          # 整个对话框抖一下，比光变红更容易注意到
            return
        self.accept()

    # ── 取值 ──
    def values(self) -> dict:
        cr = self.cb_cright.currentText().strip()
        return {
            "title": self.ed_title.text().strip(),
            "date": self.ed_date.text().strip(),
            "category": self.cb_cat.currentText().strip(),
            "tags": self.ed_tags.text().strip(),
            "cover": self.ed_cover.text().strip(),
            "description": self.ed_desc.text().strip(),
            "copyright": "" if cr == "关闭" else cr,
            "author": self.ed_author.text().strip(),
        }
