"""关于：图标 + 大版本号 + 隐私政策 + 开源许可。"""
from __future__ import annotations

import sys

import PySide6
from PySide6.QtCore import Qt, QUrl, qVersion
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout,
)

from .. import donate, licenses, theme
from ..privacy import PRIVACY_HTML
from . import badges, icons
from .dlg_about import REPO, VERSION

AUTHOR_PAGE = "https://nardofox.cn/about"
ISSUES = REPO + "/issues"


def about_text() -> str:
    """正文（不含顶部图标区）。"""
    return (
        "<h4>关于</h4>"
        "<p>给基于 <b>Hexo</b> 的博客用的桌面工具：写文章、看服务器状态、改主题配置、一键发布。"
        "全部在本机运行，不注册、不联网。</p>"
        "<p><b>主要适配 Anzhiyu（安知鱼）主题</b>：配置分组、中文说明、五个 _data 页面、"
        "发布流程都是照它做的。换 Butterfly 等其它 Hexo 主题只能算「通用兼容」——"
        "文件能读、值能改，但分组和说明未必对得上，_data 页面会缺席，"
        "发布也以你仓库里的脚本为准，不保证一切正常。</p>"

        "<h4>隐私</h4>"
        "<p>不收集、不上传任何数据；没有账号、没有遥测、没有云同步。"
        "设置只写在本机的 settings.json，备份只留在你自己的磁盘上。"
        "只有你点「采集」「发布」或关于页链接时才会联网。"
        "（完整说明见下方「隐私政策」。）</p>"

        "<h4>开源许可</h4>"
        "<p>本程序基于以下开源项目，点名字可去项目主页：</p>"
        "<ul>"
        "<li><a href='https://www.qt.io/'>Qt / PySide6</a> —— 界面基底（LGPL-3.0）</li>"
        "<li><a href='https://github.com/UN-GCPDS/qt-material'>qt-material</a> —— Material Design 2 样式（BSD-2-Clause）</li>"
        "<li><a href='https://python-markdown.github.io/'>Python-Markdown</a> —— Markdown 渲染（BSD-3-Clause）</li>"
        "<li><a href='https://pygments.org/'>Pygments</a> —— 代码高亮（BSD-2-Clause）</li>"
        "<li><a href='https://fontawesome.com/'>Font Awesome 7 Free</a> —— 图标（SIL OFL 1.1 / CC BY 4.0）</li>"
        "<li><a href='https://github.com/JetBrains/JetBrainsMono'>JetBrains Mono</a> —— 代码字体（SIL OFL 1.1）</li>"
        "<li><a href='https://github.com/notofonts/noto-cjk'>Noto Sans CJK</a> —— 正文字体（SIL OFL 1.1）</li>"
        "<li><a href='https://hexo.io/'>Hexo</a> —— 博客框架（MIT）</li>"
        "<li><a href='https://github.com/anzhiyu-c/hexo-theme-anzhiyu'>hexo-theme-anzhiyu</a> —— 主题（见项目主页）</li>"
        "<li><a href='https://github.com/jerryc127/hexo-theme-butterfly'>hexo-theme-butterfly</a> —— 主题（见项目主页）</li>"
        "</ul>"

        "<h4>反馈</h4>"
        f"<p>遇到 bug、想提建议，去项目 issue：<a href='{ISSUES}'>{ISSUES}</a><br>"
        "反馈时附上版本号、复现步骤，以及控制台/日志里的报错，会好查很多。</p>"

        "<h4>许可证</h4>"
        "<p>本项目以 <b>GPL-3.0-or-later</b> 开源：可以自由使用、修改、分发；"
        "分发修改后的版本时，需要同样以 GPL 开源并提供源代码。"
        f"<a href='{licenses.GPL_ZH_URL}'>中文说明</a></p>"

        "<h4>声明</h4>"
        "<p>软件图标是专门约的稿，<b>禁止盗用</b>。</p>"
        "<p>作者：LeonardoFox346　·　"
        f"<a href='{AUTHOR_PAGE}'>关于我</a>　·　"
        f"<a href='{REPO}'>项目主页</a></p>"
        "<p class='dim'>© 2026 LeonardoFox346</p>"
    )


class PrivacyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("隐私政策")
        self.resize(660, 640)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)
        br = QTextBrowser()
        br.setOpenExternalLinks(True)
        br.setHtml(PRIVACY_HTML)
        v.addWidget(br, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        b = QPushButton("关闭")
        b.clicked.connect(self.accept)
        row.addWidget(b)
        v.addLayout(row)


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("开源许可")
        self.resize(680, 620)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)
        br = QTextBrowser()
        br.setOpenExternalLinks(True)
        br.setPlainText(licenses.full_text())
        v.addWidget(br, 1)
        row = QHBoxLayout()
        link = QPushButton("GPL-3.0 中文说明")
        link.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(licenses.GPL_ZH_URL)))
        row.insertWidget(0, link)
        row.addStretch(1)
        row.addWidget(badges.gpl_badge(30))
        b = QPushButton("关闭")
        b.clicked.connect(self.accept)
        row.addWidget(b)
        v.addLayout(row)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.resize(620, 700)
        p = theme.c()

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(12)

        # ── 顶部：图标 + 名字 + 大版本号 ──
        head = QHBoxLayout()
        head.setSpacing(16)
        logo = QLabel()
        logo.setPixmap(icons.fox_logo(76))
        logo.setFixedSize(76, 76)
        head.addWidget(logo, 0, Qt.AlignTop)

        tv = QVBoxLayout()
        tv.setSpacing(2)
        name = QLabel("纳多狐狐的写作台")
        name.setStyleSheet(
            f"font-size:20px; font-weight:700; color:{p['ink']}; background:transparent;")
        tv.addWidget(name)

        ver = QLabel(f"版本 {VERSION}")
        ver.setStyleSheet(
            f"font-size:18px; font-weight:600; color:{p['accent']}; background:transparent;")
        ver.setToolTip("语义化版本：大版本.功能.修补")
        tv.addWidget(ver)

        based = QLabel(
            f"Based on Python {sys.version.split()[0]} · PySide6 {PySide6.__version__}"
            f" · Qt {qVersion()}")
        based.setStyleSheet(
            f"font-size:11.5px; color:{p['ink2']}; background:transparent;")
        tv.addWidget(based)

        tag = QLabel("写文章 · 服务器状态 · 主题配置 · 一键发布")
        tag.setStyleSheet(
            f"font-size:12px; color:{p['ink2']}; background:transparent;")
        tv.addWidget(tag)
        tv.addStretch(1)
        head.addLayout(tv, 1)
        root.addLayout(head)

        brow = QHBoxLayout()
        brow.setSpacing(8)
        for name, url, lic, icon, color in licenses.PROJECTS[:9]:
            lab = QLabel()
            lab.setPixmap(badges.badge(icon, color, 38, name))
            lab.setFixedSize(38, 38)
            lab.setToolTip(name + "　·　" + lic + chr(10) + url)
            brow.addWidget(lab)
        brow.addStretch(1)
        brow.addWidget(badges.gpl_badge(28))
        root.addLayout(brow)

        # ── 正文 ──
        br = QTextBrowser()
        br.setOpenExternalLinks(True)
        br.setHtml(about_text())
        br.setStyleSheet(
            f"QTextBrowser {{ background:{p['panel']}; border:1px solid {p['line']};"
            f" border-radius:8px; }}")
        root.addWidget(br, 1)

        # ── 底部 ──
        foot = QHBoxLayout()
        foot.setSpacing(8)
        b_site = QPushButton("项目主页")
        b_site.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(REPO)))
        b_author = QPushButton("作者主页")
        b_author.setToolTip(AUTHOR_PAGE)
        b_author.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(AUTHOR_PAGE)))
        b_issue = QPushButton("反馈问题")
        b_issue.setToolTip(ISSUES)
        b_issue.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(ISSUES)))
        if donate.has_any():
            b_donate = QPushButton("支持作者")
            b_donate.clicked.connect(self._donate)
            foot.addWidget(b_donate)

        b_lic = QPushButton("许可证")
        b_lic.clicked.connect(lambda: LicenseDialog(self).exec())
        b_priv = QPushButton("隐私政策")
        b_priv.clicked.connect(lambda: PrivacyDialog(self).exec())
        b_close = QPushButton("关闭")
        b_close.setObjectName("Primary")
        b_close.clicked.connect(self.accept)
        foot.addWidget(b_site)
        foot.addWidget(b_author)
        foot.addWidget(b_issue)
        foot.addWidget(b_lic)
        foot.addWidget(b_priv)
        foot.addStretch(1)
        foot.addWidget(b_close)
        root.addLayout(foot)

    def _donate(self):
        from .dlg_donate import DonateDialog
        DonateDialog(self).exec()
