"""首页：一眼看清这个工具能干什么、现在什么状态、从哪儿开始。

布局按常见开源项目主页的路子来：大标题 + 徽章 + 数据卡 + 功能卡 +
「最近文章」列表，右边一列放怎么用 / 红线 / 当前环境。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from .. import article as art
from .. import paths, publish, theme
from ..changelog import ENTRIES
from . import icons

ICON_PATH = Path(__file__).resolve().parent.parent.parent / "app.ico"

FEATURES = [
    ("pen", "写文章", "浏览 _posts、行号编辑器、文章信息、双档预览。"),
    ("server", "服务器状态", "代理四路检查 + ssh 只读采集，采完就断。"),
    ("palette", "主题配置", "472 项一个类型一块，只换值的字符。"),
    ("rocket", "发布", "构建 → 手输 YES → 部署，两处判据都过。"),
]

STEPS = [
    "写文章里选一篇，改完按 <b>Ctrl+S</b>（只改源文件）。",
    "主题配置改完点<b>保存</b>，原文件自动备份成 .bak-时间戳。",
    "发布页先<b>构建验证</b>，本地看过再一键发布。",
    "发布要<b>手输 YES</b>；<code>Deploy done</code> + 服务器 <code>✓ 部署完成</code> 才算成。",
]

RULES = [
    "改配置只替换「值」那几个字符，注释、顺序一字不动。",
    "采集是纯只读 bash，有代理时根本不连。",
    "不会自动发布：不输 YES 就不发。",
]


class ClickCard(QFrame):
    """点一下就有反应的卡片（数据卡 / 功能卡共用）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.on_click = None

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and callable(self.on_click):
            self.on_click()
        super().mouseReleaseEvent(e)


class HomePage(QWidget):
    def __init__(self, goto=None, open_settings=None, open_post=None,
                 new_post=None, open_blog=None, parent=None):
        super().__init__(parent)
        self.title = "首页"
        self.status_tip = "一眼看清状态"
        self.goto = goto or (lambda _t: None)
        self.open_settings = open_settings or (lambda: None)
        self.open_post = open_post
        self.new_post = new_post
        self.open_blog = open_blog
        self._stats: dict[str, QLabel] = {}
        self._recent_box: QVBoxLayout | None = None
        self._build()
        self.refresh()

    # ══════════ 界面 ══════════
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        host = QWidget()
        host.setObjectName("HomeHost")
        v = QVBoxLayout(host)
        v.setContentsMargins(24, 20, 24, 22)
        v.setSpacing(16)

        v.addWidget(self._build_hero())
        v.addLayout(self._build_stats())

        cols = QHBoxLayout()
        cols.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(self._section("能干什么"))
        left.addLayout(self._build_features())
        left.addWidget(self._section("最近文章"))
        recent = QWidget()
        recent.setObjectName("HomePanel")
        self._recent_box = QVBoxLayout(recent)
        self._recent_box.setContentsMargins(12, 8, 12, 10)
        self._recent_box.setSpacing(2)
        left.addWidget(recent)
        left.addStretch(1)
        cols.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self._section("怎么用"))
        right.addWidget(self._panel(self._build_steps()))
        right.addWidget(self._section("更新快报"))
        right.addWidget(self._panel(self._build_updates()))
        right.addWidget(self._section("当前环境"))
        right.addWidget(self._panel(self._build_env()))
        right.addStretch(1)
        cols.addLayout(right, 2)

        v.addLayout(cols)
        v.addStretch(1)
        scroll.setWidget(host)
        outer.addWidget(scroll)
        self.setStyleSheet(self._qss())

    def _build_hero(self) -> QWidget:
        hero = QWidget()
        hero.setObjectName("HeroCard")
        h = QHBoxLayout(hero)
        h.setContentsMargins(20, 18, 20, 18)
        h.setSpacing(16)

        logo = QLabel()
        logo.setObjectName("BrandLogo")
        logo.setFixedSize(72, 72)
        self.logo = logo
        self._set_logo()
        h.addWidget(logo, 0, Qt.AlignTop)

        tv = QVBoxLayout()
        tv.setSpacing(4)
        name = QLabel("纳多狐狐的写作台")
        name.setObjectName("HeroTitle")
        tv.addWidget(name)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_ver = QLabel("")
        self.chip_ver.setObjectName("Chip")
        self.chip_theme = QLabel("")
        self.chip_theme.setObjectName("Chip")
        chips.addWidget(self.chip_ver)
        chips.addWidget(self.chip_theme)
        chips.addStretch(1)
        tv.addLayout(chips)

        self.lbl_tag = QLabel("写文章 / 看状态 / 改配置 / 一键发布 —— 一个窗口搞定。")
        self.lbl_tag.setObjectName("Dim")
        self.lbl_tag.setWordWrap(True)
        tv.addWidget(self.lbl_tag)
        tv.addStretch(1)
        h.addLayout(tv, 1)

        btns = QGridLayout()
        btns.setHorizontalSpacing(8)
        btns.setVerticalSpacing(8)
        b1 = QPushButton("开始写文章")
        b1.setObjectName("Primary")
        b1.clicked.connect(lambda: self.goto("写文章"))
        b2 = QPushButton("去发布")
        b2.setToolTip("构建 / 部署、查看上次发布结果")
        b2.clicked.connect(lambda: self.goto("发布"))
        b3 = QPushButton("打开博客目录")
        b3.clicked.connect(lambda: self.open_blog() if self.open_blog else None)
        b4 = QPushButton("设置")
        b4.clicked.connect(lambda: self.open_settings())
        for k, b in enumerate((b1, b2, b3, b4)):
            b.setMinimumWidth(112)
            btns.addWidget(b, k // 2, k % 2)
        h.addLayout(btns)
        return hero

    def _build_stats(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        items = [("posts", "文章", "写文章"), ("dirty", "未提交改动", "发布"),
                 ("deploy", "上次发布", "发布"), ("build", "构建产物", "发布")]
        for k, (key, title, target) in enumerate(items):
            card = ClickCard()
            card.setObjectName("StatCard")
            card.on_click = lambda t=target: self.goto(t)
            cv = QVBoxLayout(card)
            cv.setContentsMargins(14, 10, 14, 10)
            cv.setSpacing(2)
            val = QLabel("—")
            val.setObjectName("StatValue")
            lab = QLabel(title)
            lab.setObjectName("Dim")
            cv.addWidget(val)
            cv.addWidget(lab)
            self._stats[key] = val
            grid.addWidget(card, 0, k)
        return grid

    def _build_features(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(10)
        for k, (icon, title, desc) in enumerate(FEATURES):
            card = ClickCard()
            card.setObjectName("HomeCard")
            card.on_click = lambda t=title: self.goto(t)
            v = QVBoxLayout(card)
            v.setContentsMargins(14, 11, 14, 11)
            v.setSpacing(4)
            top = QHBoxLayout()
            top.setSpacing(8)
            ic = QLabel()
            ic.setPixmap(icons.fa_pixmap(icon, 13, theme.c()["accent"]))
            ic.setFixedWidth(16)
            t = QLabel(title)
            t.setObjectName("CardTitle")
            top.addWidget(ic)
            top.addWidget(t)
            top.addStretch(1)
            v.addLayout(top)
            d = QLabel(desc)
            d.setObjectName("Dim")
            d.setWordWrap(True)
            v.addWidget(d)
            grid.addWidget(card, k // 2, k % 2)
        return grid

    def _build_steps(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(8)
        for k, text in enumerate(STEPS, 1):
            row = QHBoxLayout()
            row.setSpacing(8)
            num = QLabel(str(k))
            num.setObjectName("StepNum")
            num.setAlignment(Qt.AlignCenter)
            num.setFixedSize(18, 18)
            lab = QLabel(text)
            lab.setWordWrap(True)
            row.addWidget(num, 0, Qt.AlignTop)
            row.addWidget(lab, 1)
            v.addLayout(row)
        return box

    def _build_updates(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(6)
        if not ENTRIES:
            v.addWidget(QLabel("还没有更新记录"))
            return box
        e = ENTRIES[0]
        head = QHBoxLayout()
        head.setSpacing(6)
        ver = QLabel("v" + str(e["version"]))
        ver.setObjectName("Chip")
        date = QLabel(str(e["date"]))
        date.setObjectName("Dim")
        head.addWidget(ver)
        head.addWidget(date)
        head.addStretch(1)
        v.addLayout(head)
        for text in e["items"][:4]:
            lab = QLabel("· " + text)
            lab.setWordWrap(True)
            v.addWidget(lab)
        more = QPushButton("查看全部更新")
        more.setObjectName("Link")
        more.setCursor(Qt.PointingHandCursor)
        more.clicked.connect(self._show_changelog)
        v.addWidget(more)
        return box

    def _show_changelog(self):
        from PySide6.QtWidgets import QMessageBox
        lines = []
        for e in ENTRIES:
            lines.append("v%s　%s" % (e["version"], e["date"]))
            for t in e["items"]:
                lines.append("　· " + t)
            lines.append("")
        box = QMessageBox(self)
        box.setWindowTitle("更新快报")
        box.setText(chr(10).join(lines).strip())
        box.exec()

    def _build_env(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(4)
        self.env_blog = self._env_row(v, "博客")
        self.env_cfg = self._env_row(v, "配置")
        self.env_font = self._env_row(v, "字体")
        b = QPushButton("打开设置")
        b.setObjectName("Link")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self.open_settings())
        row = QHBoxLayout()
        row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        return box

    def _env_row(self, layout: QVBoxLayout, name: str) -> QLabel:
        row = QHBoxLayout()
        row.setSpacing(8)
        k = QLabel(name)
        k.setObjectName("Dim")
        k.setFixedWidth(36)
        val = QLabel("")
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(k, 0, Qt.AlignTop)
        row.addWidget(val, 1)
        layout.addLayout(row)
        return val

    def _panel(self, inner: QWidget) -> QWidget:
        inner.setObjectName("PanelInner")
        box = QWidget()
        box.setObjectName("HomePanel")
        v = QVBoxLayout(box)
        v.setContentsMargins(14, 10, 14, 12)
        v.addWidget(inner)
        return box

    def _section(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("SectionTitle")
        return lab

    # ══════════ 样式 ══════════
    def _qss(self) -> str:
        p = theme.c()
        return f"""
        QWidget#HomeHost {{ background: {p['bg']}; }}
        QLabel {{ background: transparent; }}
        QWidget#HeroCard {{ background: {p['panel']}; border: 1px solid {p['line']};
                            border-radius: 12px; }}
        QLabel#HeroTitle {{ font-size: 24px; font-weight: 700; color: {p['ink']}; }}
        QLabel#Chip {{ background: {p['chip']}; color: {p['ink2']}; border-radius: 9px;
                       padding: 1px 8px; font-size: 11px; }}
        QLabel#SectionTitle {{ font-size: 13px; font-weight: 600; color: {p['ink2']};
                               padding-top: 2px; }}
        QLabel#CardTitle {{ font-weight: 600; color: {p['ink']}; }}
        QLabel#Dim {{ color: {p['ink2']}; }}
        QLabel#StatValue {{ font-size: 21px; font-weight: 700; color: {p['accent']}; }}
        QFrame#HomeCard, QFrame#StatCard {{ background: {p['surface']};
            border: 1px solid {p['line']}; border-radius: 10px; }}
        QFrame#HomeCard:hover, QFrame#StatCard:hover {{ border: 1px solid {p['accent']}; }}
        QWidget#HomePanel {{ background: {p['surface']}; border: 1px solid {p['line']};
                             border-radius: 10px; }}
        QWidget#PanelInner {{ background: transparent; }}
        QLabel#StepNum {{ background: {p['accent_soft']}; color: {p['accent']};
                          border-radius: 9px; font-size: 11px; font-weight: 700; }}
        QPushButton#Link {{ background: transparent; border: none; color: {p['accent']};
                            padding: 0px 4px; font-size: 12px; }}
        QPushButton#RecentRow {{ text-align: left; background: transparent; border: none;
                                 padding: 6px 6px; border-radius: 6px; color: {p['ink']}; }}
        QPushButton#RecentRow:hover {{ background: {p['chip']}; }}
        """

    # ══════════ 数据 ══════════
    def _set_logo(self):
        pm = icons.fox_logo(72)
        if not pm.isNull():
            self.logo.setPixmap(pm)

    def refresh(self):
        from .dlg_about import VERSION
        self.chip_ver.setText(f"v{VERSION}　Python {sys.version.split()[0]}")
        self.chip_theme.setText(f"外观 {theme.theme_name()}")

        posts = sorted(paths.POSTS.glob("*.md")) if paths.POSTS.exists() else []
        self._stats["posts"].setText(str(len(posts)))

        try:
            dirty, n, _ = publish.worktree_dirty()
            self._stats["dirty"].setText(str(n) if dirty else "0")
        except Exception:
            self._stats["dirty"].setText("?")

        ok, msg = publish.last_publish_verdict()
        short = ""
        for token in msg.replace("　", " ").split():
            if token.count("-") == 2 and len(token) >= 10:
                short = token[5:]
                break
        self._stats["deploy"].setText(("✓ " if ok else "✗ ") + (short or "—"))

        index_html = paths.PUBLIC / "index.html"
        if index_html.exists():
            import datetime
            ts = datetime.datetime.fromtimestamp(index_html.stat().st_mtime)
            self._stats["build"].setText(ts.strftime("%m-%d %H:%M"))
        else:
            self._stats["build"].setText("未构建")

        self.env_blog.setText(str(paths.BLOG))
        self.env_cfg.setText(paths.CONFIG_YML.name)
        self.env_font.setText(f"{theme.UI_FAMILY} / {theme.MONO_FONT_FAMILY}")

        self._fill_recent()
        self.setStyleSheet(self._qss())

    def _fill_recent(self):
        if self._recent_box is None:
            return
        while self._recent_box.count():
            item = self._recent_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        try:
            posts = art.scan()[:6]
        except Exception:
            posts = []
        if not posts:
            lab = QLabel("_posts 里还没有文章")
            lab.setObjectName("Dim")
            self._recent_box.addWidget(lab)
            return
        for a in posts:
            date = (a.date or "")[:10] or "—"
            b = QPushButton(f"{date}    {a.title}")
            b.setObjectName("RecentRow")
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(str(a.path))
            if self.open_post:
                b.clicked.connect(lambda _=False, p=a.path: self.open_post(p))
            self._recent_box.addWidget(b)

    def apply_theme(self):
        self.setStyleSheet(self._qss())
        self._set_logo()
        self.refresh()
