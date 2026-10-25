"""YAML 编辑页（表单版 · 全部展开）。

一个类型一块：左边大分类，右边这块里的所有项直接铺开（不做折叠）。
布尔值给开关、固定选项给下拉、数字给窄框，其余是输入框；
说明/建议值/默认值放在鼠标悬停的气泡里。

性能：每个大分类只建一次，建完缓存；首次进入用一个半透明遮罩 + 转圈顶着，
分批建块，界面不会整页白掉。

底层仍然是 yaml_doc 的行级编辑：改值只替换值那一段字符；
增删条目只做整行插入/删除，没碰过的行一个字节不改。
"""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QCursor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QMenu, QScrollArea, QSizePolicy, QSplitter, QStyle, QStyledItemDelegate,
    QToolTip, QVBoxLayout, QWidget,
)

from .. import theme
from ..labels import DESC, ENUMS, RANGE, human
from ..paths import CONFIG_GROUPS
from ..yaml_doc import YamlDoc, tip_of
from ..yaml_tree import Node, YamlTree
from . import anim, icons

SILENT = os.environ.get("ND_SILENT") == "1"     # 自动化测试时跳过弹窗


def _confirm(parent, title: str, text: str) -> bool:
    if SILENT:
        return True
    return QMessageBox.question(parent, title, text) == QMessageBox.Yes


def _say(parent, title: str, text: str):
    if SILENT:
        print("[dialog]", title, "|", text.splitlines()[0] if text else "")
        return
    QMessageBox.information(parent, title, text)


def _warn(parent, title: str, text: str):
    if SILENT:
        print("[warn]", title, "|", text.splitlines()[0] if text else "")
        return
    QMessageBox.critical(parent, title, text)


# 列表被清空后还要能加回来：给已知列表一个骨架
ITEM_SHAPES = {
    "link_list": [("name", ""), ("link", ""), ("avatar", ""), ("descr", "")],
    "creativity_list": [("name", ""), ("color", ""), ("icon", "")],
    "album_list": [("date", ""), ("content", ""), ("image", "")],
    "equipment_list": [("name", ""), ("specification", ""), ("description", ""),
                       ("image", ""), ("link", "")],
    "good_things": [("title", ""), ("description", ""), ("equipment_list", "")],
}

LIST_CN = {
    "link_list": "友链条目", "creativity_list": "技能条目",
    "album_list": "照片", "equipment_list": "装备条目", "good_things": "装备分组",
    "image": "图片地址",
}


# ══════════════ 开关 ══════════════
class Switch(QAbstractButton):
    """圆角滑轨 + 滑块。QSS 画不出跟着动画走的滑块，只能自绘。"""

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(bool(checked))
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(42, 22)
        self._pos = 1.0 if checked else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(130)
        self._anim.valueChanged.connect(self._tick)
        self.toggled.connect(self._slide)

    def _slide(self, on: bool):
        self._anim.stop()
        self._anim.setStartValue(float(self._pos))
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def _tick(self, v):
        self._pos = float(v)
        self.update()

    def paintEvent(self, event):
        p = theme.c()
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing, True)
        h, w = self.height(), self.width()
        g.setPen(Qt.NoPen)
        g.setBrush(QColor(p["accent"] if self.isChecked() else p["line"]))
        g.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        d = h - 6
        x = 3 + (w - h) * self._pos
        g.setBrush(QColor("#FFFFFF"))
        g.drawEllipse(int(x), 3, d, d)

    def sizeHint(self):
        return QSize(42, 22)


# ══════════════ 大分类列表 ══════════════
class CatDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        p = theme.c()
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        if selected or hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(p["accent_soft"] if selected else p["chip"]))
            painter.drawRoundedRect(r.adjusted(4, 2, -4, -2), 7, 7)
        painter.setPen(QColor(p["ink"] if selected else p["ink2"]))
        painter.setFont(theme.ui_font(9.5, bold=selected))
        name = index.data(Qt.DisplayRole) or ""
        cnt = index.data(Qt.UserRole + 1)
        painter.drawText(r.adjusted(14, 0, -48, 0), Qt.AlignVCenter | Qt.AlignLeft, name)
        if cnt not in (None, ""):
            painter.setFont(theme.mono_font(8.5))
            painter.setPen(QColor(p["ink2"]))
            painter.drawText(r.adjusted(0, 0, -12, 0), Qt.AlignVCenter | Qt.AlignRight, str(cnt))
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(0, 32)


# ══════════════ 载入遮罩 ══════════════
class Busy(QWidget):
    """盖在表单上的一块半透明遮罩 + 转圈。只在首次建某个分类时出现。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("Busy")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.spinner = anim.Spinner(self, size=24)
        row.addWidget(self.spinner)
        self.label = QLabel("载入中…")
        self.label.setObjectName("BusyText")
        row.addWidget(self.label)
        row.addStretch(1)
        v.addLayout(row)
        v.addStretch(1)
        self.hide()

    def cover(self, widget: QWidget):
        self.setParent(widget)
        self.setGeometry(widget.rect())
        self.raise_()
        self.show()
        self.spinner.start()

    def done(self):
        self.spinner.stop()
        self.hide()


# ══════════════ 页面 ══════════════
class YamlPage(QWidget):
    """配置页与 5 个数据页共用。grouped=True 时按 CONFIG_GROUPS 分类。"""

    def __init__(self, title: str, path, grouped: bool = False,
                 show_raw: bool = False, parent=None):
        super().__init__(parent)
        self.title = title
        self.status_tip = "一个类型一块　·　保存前自动备份，方便回滚"
        self.path = path
        self.grouped = grouped
        self.show_raw = show_raw
        self.doc: YamlDoc | None = None
        self.tree: YamlTree | None = None
        self.snapshot: list[str] = []
        self.cache: dict = {}          # 分类 -> 已经建好的页面
        self._jobs: list = []
        self._page: QWidget | None = None
        self._page_key = None
        self._build_id = 0
        self._build()
        self.reload()

    # ── 界面骨架 ──
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 10)
        root.setSpacing(8)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜键名 / 中文名 / 值")
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(self._on_search)
        bar.addWidget(self.search)

        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("Primary")
        self.btn_save.setFixedWidth(84)
        self.btn_save.clicked.connect(self.save)
        bar.addWidget(self.btn_save)

        self.btn_revert = QPushButton("还原")
        self.btn_revert.setFixedWidth(84)
        self.btn_revert.clicked.connect(self.revert)
        bar.addWidget(self.btn_revert)

        self.btn_rollback = QPushButton("回滚…")
        self.btn_rollback.setFixedWidth(84)
        self.btn_rollback.setToolTip("用之前保存时留下的 .bak 备份覆盖当前文件")
        self.btn_rollback.clicked.connect(self.show_rollbacks)
        bar.addWidget(self.btn_rollback)

        if self.show_raw:
            self.btn_raw = QPushButton("原文")
            self.btn_raw.setFixedWidth(72)
            self.btn_raw.setToolTip("看这个 yml 的原始内容（只读）")
            self.btn_raw.clicked.connect(self.show_raw_text)
            bar.addWidget(self.btn_raw)

        self.info = QLabel("")
        bar.addWidget(self.info)
        bar.addStretch(1)
        root.addLayout(bar)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(8)

        # 左：大分类
        left = QWidget()
        left.setFixedWidth(214)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)
        self.cats = QListWidget()
        self.cats.setObjectName("Cat")
        self.cats.setFrameShape(QFrame.NoFrame)
        self.cats.setItemDelegate(CatDelegate(self.cats))
        self.cats.setMouseTracking(True)
        self.cats.currentRowChanged.connect(self._on_cat)
        lv.addWidget(self.cats, 1)

        self.cat_tools = QWidget()
        tv = QHBoxLayout(self.cat_tools)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.setSpacing(4)
        self.btn_add_group = QPushButton()
        self.btn_add_group.setIcon(icons.fa_icon("square-plus", 18, theme.c()["ink"]))
        self.btn_add_group.setIconSize(QSize(18, 18))
        self.btn_add_group.setFixedSize(36, 32)
        self.btn_add_group.setToolTip("新建一个大分类")
        self.btn_add_group.clicked.connect(self.add_group)
        self.btn_del_group = QPushButton()
        self.btn_del_group.setIcon(icons.fa_icon("trash-can", 18, theme.c()["ink"]))
        self.btn_del_group.setIconSize(QSize(18, 18))
        self.btn_del_group.setFixedSize(36, 32)
        self.btn_del_group.setToolTip("删掉当前这个大分类")
        self.btn_del_group.clicked.connect(self.del_group)
        self.btn_up = QPushButton()
        self.btn_up.setIcon(icons.fa_icon("arrow-up", 18, theme.c()["ink"]))
        self.btn_up.setIconSize(QSize(18, 18))
        self.btn_up.setFixedSize(36, 32)
        self.btn_up.setToolTip("上移")
        self.btn_up.clicked.connect(lambda: self.move_group(-1))
        self.btn_down = QPushButton()
        self.btn_down.setIcon(icons.fa_icon("arrow-down", 18, theme.c()["ink"]))
        self.btn_down.setIconSize(QSize(18, 18))
        self.btn_down.setFixedSize(36, 32)
        self.btn_down.setToolTip("下移")
        self.btn_down.clicked.connect(lambda: self.move_group(1))
        for b in (self.btn_add_group, self.btn_del_group, self.btn_up, self.btn_down):
            tv.addWidget(b)
        lv.addWidget(self.cat_tools)
        self.cat_tools.setVisible(not self.grouped)
        split.addWidget(left)

        # 右：表单（页面切换靠换 child，不重建已建好的）
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.host = QWidget()
        self.host_lay = QVBoxLayout(self.host)
        self.host_lay.setContentsMargins(14, 4, 14, 18)
        self.host_lay.setSpacing(8)
        self.scroll.setWidget(self.host)
        split.addWidget(self.scroll)
        split.setSizes([214, 1100])
        root.addWidget(split, 1)

        self.busy = Busy(self.scroll.viewport())
        self.setStyleSheet(self._qss())

    def _qss(self) -> str:
        p = theme.c()
        # QWidget 一律透明：全局 QSS 会给每个 QWidget 刷一层 page 底色，
        # 卡片里的标签/行就会各自带一块深色方块（就是「文字底下的黑框」）。
        return f"""
        QWidget#Row, QWidget#BlockBody, QWidget#SubHeadBox, QWidget#SwitchBox,
        QWidget#ListSection, QWidget#CardHead {{ background: transparent; }}
        QWidget#Block {{ background: {p['surface']}; border: 1px solid {p['line']};
                         border-radius: 8px; }}
        QWidget#BlockHead {{ background: {p['panel']};
                             border-top-left-radius: 7px;
                             border-top-right-radius: 7px; }}
        QWidget#Card {{ background: {p['panel']}; border: 1px solid {p['line']};
                        border-radius: 8px; }}
        QWidget#Busy {{ background: {p['bg']}; }}
        QLabel {{ background: transparent; }}
        QLabel#Dim {{ color: {p['ink2']}; }}
        QLabel#KeyName {{ color: {p['ink2']};
                           font-family: "{theme.MONO_FONT_FAMILY}"; }}
        QLabel#BlockTitle {{ color: {p['ink']}; font-weight: 600; }}
        QLabel#Badge {{ color: {p['ink2']}; font-size: 11px; }}
        QLabel#SubHead {{ color: {p['ink2']}; font-weight: 600; font-size: 11px;
                          padding-top: 4px; }}
        QLabel#Section {{ color: {p['accent']}; font-weight: 600; font-size: 12px;
                          padding: 10px 2px 2px 2px; }}
        QLabel#BusyText {{ color: {p['ink2']}; font-size: 12px; padding-left: 6px; }}
        QLineEdit, QComboBox {{ background: {p['field']}; border: 1px solid {p['line']};
                                border-radius: 6px; padding: 2px 8px; color: {p['ink']}; }}
        QLineEdit:focus, QComboBox:focus {{ border: 1px solid {p['accent']}; }}
        QPushButton#Link {{ background: transparent; border: none; color: {p['accent']};
                            padding: 0px 6px; font-size: 12px; }}
        QPushButton#Link:hover {{ color: {p['ink']}; }}
        QPushButton#Danger {{ background: transparent; border: none; color: {p['bad']};
                              padding: 0px 6px; font-size: 12px; }}
        QPushButton#Danger:hover {{ color: {p['ink']}; }}
        QListWidget#Cat {{ background: {p['panel']}; border: 1px solid {p['line']};
                           border-radius: 8px; outline: 0; padding: 6px 4px; }}
        QListWidget#Cat::item {{ border: none; background: transparent; }}
        """

    # ── 读取 ──
    def reload(self):
        self.doc = YamlDoc(self.path)
        self.tree = YamlTree(self.doc)
        # 根不是列表（比如 Hexo 的 _config.yml）就没法「加/删分类」，把按钮藏起来
        self.cat_tools.setVisible(not self.grouped and bool(self.tree.root_items()))
        self.snapshot = list(self.doc.lines)
        self._invalidate()
        self._fill_cats()
        self._render()

    def _invalidate(self):
        for page in self.cache.values():
            try:
                page.setParent(None)
                page.deleteLater()
            except RuntimeError:
                pass
        self.cache.clear()
        while self.host_lay.count():
            item = self.host_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._page = None

    def _group_of(self, top: str) -> str:
        if not self.grouped:
            return ""
        for gname, keys in CONFIG_GROUPS:
            if top in keys.split():
                return gname
        return "其它"

    def _cats_data(self) -> list[tuple[str, object, int]]:
        out = []
        if self.doc is None or self.tree is None:
            return out
        if self.grouped:
            tops = self.tree.top_nodes()
            counts: dict[str, int] = {}
            for n in tops:
                g = self._group_of(n.key)
                counts[g] = counts.get(g, 0) + len(self.tree.leaves_of(n))
            order = [g for g, _ in CONFIG_GROUPS]
            if "其它" not in order:
                order.append("其它")
            for g in order:
                if counts.get(g, 0):
                    out.append((g, g, counts[g]))
        else:
            items = self.tree.root_items()
            if items:
                for k, item in enumerate(items):
                    n = item.child("class_name")
                    name = n.value if n is not None and n.value else f"项目 {k + 1}"
                    out.append((name, k, len(self.tree.leaves_of(item))))
            else:
                # 根是 map（比如 Hexo 的 _config.yml）：一级键当分类
                for k, node in enumerate(self.tree.top_nodes()):
                    out.append((node.key, k, len(self.tree.leaves_of(node))))
        return out

    def _fill_cats(self):
        keep = self.cats.currentRow()
        self.cats.blockSignals(True)
        self.cats.clear()
        for name, key, count in self._cats_data():
            it = QListWidgetItem(name)
            it.setData(Qt.UserRole, key)
            it.setData(Qt.UserRole + 1, count)
            it.setData(Qt.UserRole + 2, count)
            it.setSizeHint(QSize(0, 32))
            self.cats.addItem(it)
        self.cats.blockSignals(False)
        if self.cats.count():
            self.cats.setCurrentRow(min(max(keep, 0), self.cats.count() - 1))

    def _current_key(self):
        it = self.cats.currentItem()
        return it.data(Qt.UserRole) if it else None

    # ── 渲染调度 ──
    def _on_cat(self, *_):
        self._render()

    def _on_search(self, *_):
        self._render()

    def _render(self, *_):
        if self.doc is None:
            return
        q = self.search.text().strip()
        key = ("search", q) if q else ("cat", self._current_key())
        self._update_cat_counts()
        page = self.cache.get(key)
        if page is not None:
            self._show_page(page, key)
            self._update_info()
            return
        self._start_build(key, q)

    def _show_page(self, page: QWidget, key):
        self._build_id += 1              # 取消还在排队的老构建
        self.busy.done()
        if self._page is page and page.isVisible():
            self._update_info()
            return
        for other in self.cache.values():
            if other is not page:
                other.setVisible(False)
        page.setVisible(True)
        self._page = page
        self._page_key = key
        self.scroll.verticalScrollBar().setValue(0)
        QToolTip.hideText()

    def _start_build(self, key, q: str):
        # 搜索页只留最新一份，别把每次按键都缓存住
        if q:
            for k in list(self.cache):
                if isinstance(k, tuple) and k[0] == "search" and k != key:
                    old = self.cache.pop(k)
                    try:
                        old.setParent(None)
                        old.deleteLater()
                    except RuntimeError:
                        pass
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self._jobs = self._make_jobs(lay, q)
        self._page = page
        self._page_key = key
        self._pending_key = key
        page.setParent(self.host)
        self.host_lay.addWidget(page)
        page.hide()
        self.busy.cover(self.scroll.viewport())
        self._build_id += 1
        bid = self._build_id
        QTimer.singleShot(0, lambda: self._pump(bid))

    def _pump(self, bid: int):
        if bid != self._build_id:
            return
        t0 = time.monotonic()
        while self._jobs and time.monotonic() - t0 < 0.012:
            job = self._jobs.pop(0)
            job()
        if self._jobs:
            QTimer.singleShot(0, lambda: self._pump(bid))
            return
        page = self._page
        if page is not None:
            self.cache[self._pending_key] = page
            self._show_page(page, self._pending_key)
        self.busy.done()
        QToolTip.hideText()
        self._update_info()

    # ── 建页面：把工作拆成一个个小任务 ──
    def _make_jobs(self, lay: QVBoxLayout, q: str) -> list:
        jobs: list = []
        add = lay.addWidget

        def job(fn):
            jobs.append(fn)

        if self.grouped:
            nodes = self.tree.top_nodes()
            if q:
                groups = []
                for g, _ in CONFIG_GROUPS:
                    picked = []
                    for node in nodes:
                        if self._group_of(node.key) != g:
                            continue
                        leaves = [lf for lf in self.tree.leaves_of(node) if self._match(lf)]
                        if leaves:
                            picked.append((node, leaves))
                    if picked:
                        groups.append((g, picked))
                for g, picked in groups:
                    job(lambda g=g: add(self._section(g)))
                    for node, leaves in picked:
                        job(lambda node=node, leaves=leaves: add(self._block(node, leaves)))
            else:
                cat = self._current_key()
                for node in nodes:
                    if self._group_of(node.key) != cat:
                        continue
                    leaves = self.tree.leaves_of(node)
                    if leaves:
                        job(lambda node=node, leaves=leaves: add(self._block(node, leaves)))
        else:
            items = self.tree.root_items()
            if q:
                for item in items:
                    leaves = [lf for lf in self.tree.leaves_of(item) if self._match(lf)]
                    if not leaves:
                        continue
                    job(lambda item=item: add(self._section(self._group_name(item))))
                    job(lambda item=item: add(self._block(
                        item, [n.leaf for n in item.scalars() if self._match(n.leaf)],
                        title_override="基本信息")))
                    for child in item.children:
                        if child.kind == "list":
                            hits = [n for n in child.children
                                    if any(self._match(lf) for lf in self.tree.leaves_of(n))]
                            if hits:
                                job(lambda child=child, hits=hits:
                                    add(self._list_section(child, items=hits)))
                        elif child.kind == "map":
                            job(lambda child=child: self._add_maybe(add, self._map_block(child)))
            else:
                k = self._current_key()
                if not isinstance(k, int) or not (0 <= k < len(items)):
                    tops = self.tree.top_nodes()
                    if not isinstance(k, int) or not (0 <= k < len(tops)):
                        job(lambda: add(self._empty("左边选一个大分类")))
                        return jobs
                    node = tops[k]
                    if node.is_scalar:
                        job(lambda node=node: add(self._block(node, [node.leaf])))
                    elif node.kind == "list":
                        job(lambda node=node: add(self._list_section(node)))
                    else:
                        job(lambda node=node: self._add_maybe(add, self._map_block(node)))
                    job(lambda: lay.addStretch(1))
                    return jobs
                item = items[k]
                job(lambda: add(self._block(
                    item, [n.leaf for n in item.scalars()],
                    title_override="基本信息")))
                for child in item.children:
                    if child.kind == "list":
                        job(lambda child=child: add(self._list_section(child)))
                    elif child.kind == "map":
                        job(lambda child=child: self._add_maybe(add, self._map_block(child)))
        if q and not jobs:
            job(lambda: add(self._empty(f"全文没有「{q}」")))
        if not jobs:
            job(lambda: add(self._empty("这一页没有可编辑项")))
        job(lambda: lay.addStretch(1))
        return jobs

    def _match(self, leaf) -> bool:
        q = self.search.text().strip().lower()
        if not q:
            return True
        return (q in leaf.path.lower() or q in leaf.value.lower()
                or q in human(leaf.key).lower()
                or q in str(leaf.comment or "").lower())

    # ── 小部件 ──
    def _section(self, text: str) -> QWidget:
        w = QLabel(text)
        w.setObjectName("Section")
        return w

    def _empty(self, text: str) -> QWidget:
        w = QLabel(text)
        w.setObjectName("Dim")
        w.setAlignment(Qt.AlignCenter)
        w.setMinimumHeight(80)
        return w

    def _block(self, node: Node, leaves, title_override: str = "",
               bare: bool = False) -> QWidget:
        box = QWidget()
        box.setObjectName("Block")
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 6)
        v.setSpacing(0)

        head = QWidget()
        head.setObjectName("BlockHead")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 7, 12, 6)
        hl.setSpacing(8)
        title = QLabel(title_override or human(node.key))
        title.setObjectName("BlockTitle")
        hl.addWidget(title)
        raw = node.key if not title_override else ""
        if raw and raw != title.text():
            rk = QLabel(raw)
            rk.setObjectName("KeyName")
            hl.addWidget(rk)
        hl.addStretch(1)
        if len(leaves) > 1:
            badge = QLabel(f"{len(leaves)} 项")
            badge.setObjectName("Badge")
            hl.addWidget(badge)
        if bare:
            head.setVisible(False)
        else:
            v.addWidget(head)

        body = QWidget()
        body.setObjectName("BlockBody")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(12, 0, 12, 0)
        bv.setSpacing(0)
        last_sub = None
        for lf in leaves:
            parent = lf.parent or ""
            sub = parent.split(".")[-1] if parent else ""
            if parent and sub and sub != node.key and sub != last_sub:
                bv.addWidget(self._sub_head(human(sub)))
                last_sub = sub
            bv.addWidget(self._row(lf, plain=True))
        v.addWidget(body)
        return box

    @staticmethod
    def _add_maybe(add, widget):
        if widget is not None:
            add(widget)

    def _map_block(self, node: Node, level: int = 0) -> QWidget | None:
        """数据页里嵌套的一小类（avatarSkills / aboutsiteTips / careers…）。"""
        leaves = [lf for lf in self.tree.leaves_of(node) if self._match(lf)]
        if not leaves:
            return None
        box = QWidget()
        box.setObjectName("Block")
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 6)
        v.setSpacing(0)

        head = QWidget()
        head.setObjectName("BlockHead")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 7, 12, 6)
        hl.setSpacing(8)
        title = QLabel(human(node.key))
        title.setObjectName("BlockTitle")
        hl.addWidget(title)
        if human(node.key) != node.key:
            rk = QLabel(node.key)
            rk.setObjectName("KeyName")
            hl.addWidget(rk)
        hl.addStretch(1)
        if len(leaves) > 1:
            badge = QLabel(f"{len(leaves)} 项")
            badge.setObjectName("Badge")
            hl.addWidget(badge)
        v.addWidget(head)

        body = QWidget()
        body.setObjectName("BlockBody")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(12, 0, 12, 0)
        bv.setSpacing(0)
        for child in node.children:
            if child.is_scalar:
                if self._match(child.leaf):
                    bv.addWidget(self._row(child.leaf, plain=True))
            elif child.kind == "list":
                hits = [n for n in child.children
                        if any(self._match(lf) for lf in self.tree.leaves_of(n))]
                if hits:
                    bv.addWidget(self._list_section(child, level + 1, items=hits))
            elif child.kind == "map":
                sub = self._map_block(child, level + 1)
                if sub is not None:
                    bv.addWidget(sub)
        v.addWidget(body)
        return box

    def _sub_head(self, text: str) -> QWidget:
        w = QWidget()
        w.setObjectName("SubHeadBox")
        h = QHBoxLayout(w)
        h.setContentsMargins(2, 10, 2, 2)
        lab = QLabel(text)
        lab.setObjectName("SubHead")
        h.addWidget(lab)
        h.addStretch(1)
        return w

    def _tip(self, leaf) -> str:
        base = tip_of(leaf)
        d = DESC.get(leaf.path) or DESC.get(leaf.key) or ""
        parts = [x for x in ([d, base] if d and d not in base else [base]) if x]
        # 只给「推荐值 / 可选值」：默认值对 path、名称、图标这种一眼就该自己填的没意义，
        # 而且以前那行写的其实就是当前值，纯属干扰。开关项不加，界面本身就是状态。
        if leaf.kind != "bool":
            opts = ENUMS.get(leaf.path) or ENUMS.get(leaf.key)
            rng = RANGE.get(leaf.path) or RANGE.get(leaf.key)
            if opts:
                names = "、".join(v if v == n else f"{v}（{n}）" for v, n in opts if v)
                if names:
                    parts.append("可选值：" + names)
            elif rng:
                parts.append(f"推荐值：{rng[2]}")
            elif not (leaf.value or "").strip():
                parts.append("推荐值：留空 = 用主题默认（一般是关/不显示）")
        return "\n\n".join(parts).strip()

    def _label_of(self, leaf) -> str:
        key = human(leaf.key)
        parent = (leaf.parent or "").split(".")[-1]
        if parent and parent not in ("", leaf.key):
            pk = human(parent)
            if pk and pk != parent:
                return f"{pk} · {key}"
        return key

    def _row(self, leaf, indent: int = 0, plain: bool = False) -> QWidget:
        w = QWidget()
        w.setObjectName("Row")
        # 输入框 30 + 上下各 3px 边距 = 36；行高必须给够，不然底边会被裁掉
        w.setFixedHeight(36)
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 3, 0, 3)
        h.setSpacing(10)
        if indent:
            h.addSpacing(indent)
        lab = QLabel(human(leaf.key) if plain else self._label_of(leaf))
        lab.setMinimumWidth(196)
        lab.setMaximumWidth(196)
        tip = self._tip(leaf)
        lab.setToolTip(tip)              # 气泡只挂在文字上，输入框不挂 —— 免得切换分类时乱弹
        h.addWidget(lab)

        if human(leaf.key) != leaf.key:
            k = QLabel(leaf.key)
            k.setObjectName("KeyName")
            k.setToolTip(tip)
            k.setFixedWidth(200)
            # 键名太长就省略，别把输入框挤没了
            k.setText(QFontMetrics(theme.mono_font(10.5)).elidedText(
                leaf.key, Qt.ElideRight, 192))
            h.addWidget(k)
        else:
            h.addSpacing(200)

        ctl = self._control(leaf)
        if leaf.kind in ("bool", "num") or ENUMS.get(leaf.key):
            h.addStretch(1)          # 开关 / 数字 / 下拉：靠右，保持一列
            h.addWidget(ctl)
        else:
            h.addWidget(ctl, 1)      # 文本：占满剩下的宽度，长 URL 也看得全
        return w

    def _control(self, leaf, width: int = 360) -> QWidget:
        if leaf.kind == "bool":
            box = QWidget()
            box.setObjectName("SwitchBox")
            bh = QHBoxLayout(box)
            bh.setContentsMargins(0, 0, 0, 0)
            bh.setSpacing(8)
            sw = Switch(leaf.is_true)
            lab = QLabel("开" if leaf.is_true else "关")
            lab.setObjectName("Dim")
            sw.toggled.connect(lambda on, lf=leaf, lab=lab: self._set_bool(lf, on, lab))
            bh.addWidget(sw)
            bh.addWidget(lab)
            bh.addStretch(1)
            box.setFixedWidth(width)
            box.setFixedHeight(24)
            return box

        opts = ENUMS.get(leaf.key) or []
        if opts:
            cb = QComboBox()
            for v, n in opts:
                cb.addItem(n, v)
            cur = leaf.value
            idx = next((i for i, (v, _) in enumerate(opts) if v == cur), -1)
            if idx < 0 and cur:
                cb.addItem(f"{cur}（当前）", cur)
                idx = cb.count() - 1
            cb.setCurrentIndex(max(0, idx))
            cb.setFixedWidth(width)
            cb.setFixedHeight(30)
            cb.currentIndexChanged.connect(
                lambda _i, cb=cb, lf=leaf: self._set_value(lf, cb.currentData()))
            return cb

        ed = QLineEdit(leaf.value)
        if leaf.kind == "num":
            ed.setFixedWidth(120)
        else:
            ed.setMinimumWidth(280)
            ed.setMaximumWidth(4000)
            ed.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ed.setFixedHeight(30)
        ed.setCursorPosition(0)
        if leaf.value == "":
            ed.setPlaceholderText("留空即可" if leaf.kind == "str" else "留空 = 关")
        ed.textEdited.connect(lambda txt, lf=leaf: self._set_value(lf, txt))
        return ed

    # ── 列表 ──
    def _add_button(self, lst: Node) -> QPushButton:
        b = QPushButton("+ 添加一条")
        b.setObjectName("Link")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _=False, lst=lst: self.add_item(lst))
        return b

    def _list_section(self, lst: Node, level: int = 0, items=None) -> QWidget:
        items = list(lst.children) if items is None else list(items)
        name = LIST_CN.get(lst.key, human(lst.key))

        cards = QWidget()
        cards.setObjectName("ListSection")
        cv = QVBoxLayout(cards)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(6)
        if not items:
            cv.addWidget(self._empty("还没有条目，点「添加一条」"))
        else:
            for k, item in enumerate(items):
                cv.addWidget(self._item_card(lst, item, k, level))

        if level > 0:
            # 卡片里的子列表：轻量小标题，不再套一层块
            box = QWidget()
            box.setObjectName("ListSection")
            v = QVBoxLayout(box)
            v.setContentsMargins(14, 4, 0, 4)
            v.setSpacing(4)
            head = QWidget()
            hh = QHBoxLayout(head)
            hh.setContentsMargins(0, 0, 0, 0)
            hh.setSpacing(8)
            title = QLabel(f"{name}（{len(items)} 条）")
            title.setObjectName("BlockTitle")
            hh.addWidget(title)
            hh.addWidget(self._add_button(lst))
            hh.addStretch(1)
            v.addWidget(head)
            v.addWidget(cards)
            return box

        # 顶层列表：和配置页的块一样，灰标题条 + 灰底
        box = QWidget()
        box.setObjectName("Block")
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 6)
        v.setSpacing(0)
        head = QWidget()
        head.setObjectName("BlockHead")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 7, 12, 6)
        hl.setSpacing(8)
        title = QLabel(name)
        title.setObjectName("BlockTitle")
        hl.addWidget(title)
        hl.addWidget(self._add_button(lst))
        hl.addStretch(1)
        badge = QLabel(f"{len(items)} 条")
        badge.setObjectName("Badge")
        hl.addWidget(badge)
        v.addWidget(head)

        body = QWidget()
        body.setObjectName("BlockBody")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(12, 8, 12, 4)
        bv.setSpacing(6)
        bv.addWidget(cards)
        v.addWidget(body)
        return box

    def _card_title(self, item: Node, k: int) -> str:
        """只写「项目 N」。名字改了这张卡不会跟着变，所以干脆不显示。"""
        return f"项目 {k + 1}"

    def _item_card(self, lst: Node, item: Node, k: int, level: int) -> QWidget:
        card = QWidget()
        card.setObjectName("Card")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(10, 6, 10, 8)
        cv.setSpacing(0)

        head = QWidget()
        head.setObjectName("CardHead")
        hh = QHBoxLayout(head)
        hh.setContentsMargins(0, 0, 0, 4)
        hh.setSpacing(8)
        title = QLabel(self._card_title(item, k))
        title.setObjectName("BlockTitle")
        hh.addWidget(title)
        hh.addStretch(1)
        if item.kind == "scalar":
            ed = QLineEdit(item.value)
            ed.setFixedWidth(420)
            ed.setCursorPosition(0)
            ed.textEdited.connect(lambda txt, lf=item.leaf: self._set_value(lf, txt))
            hh.addWidget(ed)
        dele = QPushButton("删除本条")
        dele.setObjectName("Danger")
        dele.setCursor(Qt.PointingHandCursor)
        dele.clicked.connect(lambda _=False, it=item, b=None: self._ask_delete(it, card))
        hh.addWidget(dele)
        cv.addWidget(head)

        if item.kind == "scalar":
            return card

        for child in item.children:
            if child.is_scalar:
                cv.addWidget(self._row(child.leaf, plain=True))
            elif child.kind == "list":
                cv.addWidget(self._list_section(child, level + 1))
            elif not child.children and child.key in ITEM_SHAPES:
                empty = Node("list", child.key, child.line, child.line, child.line,
                             child.indent, list_indent=child.indent + 2)
                cv.addWidget(self._list_section(empty, level + 1))
        return card

    def _ask_delete(self, item: Node, card: QWidget):
        """删除走行内确认，不弹模态窗。"""
        if getattr(card, "_confirming", False):
            return
        card._confirming = True
        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 4, 0, 0)
        h.setSpacing(8)
        lab = QLabel("删掉这一条？只改内存，点「保存」才写文件。")
        lab.setObjectName("Dim")
        h.addWidget(lab)
        h.addStretch(1)
        yes = QPushButton("删除")
        yes.setObjectName("Danger")
        no = QPushButton("取消")
        no.setObjectName("Link")
        for b in (yes, no):
            b.setCursor(Qt.PointingHandCursor)
            h.addWidget(b)
        card.layout().addWidget(bar)

        def cancel():
            card._confirming = False
            bar.setParent(None)
            bar.deleteLater()

        def do():
            self._delete_now(item)

        yes.clicked.connect(lambda _=False: do())
        no.clicked.connect(lambda _=False: cancel())

    # ── 编辑动作 ──
    def _set_value(self, leaf, text: str):
        if self.doc is None or leaf is None:
            return
        self.doc.set_value(leaf, str(text))
        # 分类名、条目名这种「会显示在别处」的值，改完立刻同步，不等重建
        if leaf.key == "class_name" and not self.grouped:
            it = self.cats.currentItem()
            if it is not None:
                name = str(text).strip() or f"项目 {self.cats.currentRow() + 1}"
                it.setText(name)
        self._update_info()

    def _set_bool(self, leaf, on: bool, lab: QLabel):
        self._set_value(leaf, "true" if on else "false")
        lab.setText("开" if on else "关")

    def _delete_now(self, item: Node):
        if self.tree is None:
            return
        self.tree.remove(item)
        self._after_structure()

    def add_item(self, lst: Node):
        if self.tree is None:
            return
        ok = self.tree.add_item(lst, shape=ITEM_SHAPES.get(lst.key))
        if ok:
            self._after_structure()
        else:
            _say(self, "提示", "这一项没法自动加，先手动补一条到文件里。")

    def add_group(self):
        if self.tree is None or self.grouped:
            return
        items = self.tree.root_items()
        if not items:
            _say(self, "提示", "这个文件不是列表结构，加不了大分类。")
            return
        tpl = items[-1]
        lines = self._blank_group_lines(tpl)
        if not lines:
            return
        self.tree.insert_after(tpl, lines)
        self._after_structure(select_last=True)

    def _next_group_name(self) -> str:
        names = set()
        if self.tree is not None:
            for it in self.tree.root_items():
                n = it.child("class_name")
                if n is not None and n.value:
                    names.add(n.value)
        k = len(self.tree.root_items()) + 1 if self.tree is not None else 1
        while f"新分类 {k}" in names:
            k += 1
        return f"新分类 {k}"

    def _blank_group_lines(self, tpl: Node) -> list[str]:
        lines = self.tree.doc.lines
        drop = set()

        def walk(node):
            for c in node.children:
                if c.kind == "list":
                    for extra in c.children[1:]:
                        drop.update(range(extra.start, extra.end))
                elif c.kind == "map":
                    walk(c)

        walk(tpl)
        seg = [lines[k] for k in range(tpl.start, tpl.end) if k not in drop]
        for lf in self.tree.leaves_of(tpl):
            k = lf.line - tpl.start
            if not (0 <= k < len(seg)) or lf.line in drop:
                continue
            line = seg[k]
            if lf.vstart <= lf.vend <= len(line):
                seg[k] = line[:lf.vstart] + '""' + line[lf.vend:]
        name = self._next_group_name()
        for k, line in enumerate(seg):
            if line.lstrip().startswith("- class_name:"):
                idx = line.index(":", line.index("class_name")) + 1
                seg[k] = line[:idx] + " " + name
                break
        while seg and not seg[-1].strip():
            seg.pop()
        return seg

    def del_group(self):
        if self.tree is None or self.grouped:
            return
        k = self._current_key()
        items = self.tree.root_items()
        if not isinstance(k, int) or not (0 <= k < len(items)):
            return
        item = items[k]
        name = self._group_name(item)
        if len(items) <= 1:
            _say(self, "提示", "只剩最后一个大分类了，删掉文件就空了。")
            return
        if not _confirm(self, "删掉这个大分类？",
                        f"{name}\n\n会删掉它下面的所有条目。只在内存里删，点「保存」才写进文件。"):
            return
        self.tree.remove(item)
        self._after_structure()

    def move_group(self, delta: int):
        if self.tree is None or self.grouped:
            return
        k = self._current_key()
        items = self.tree.root_items()
        if not isinstance(k, int) or not (0 <= k < len(items)):
            return
        if self.tree.move(items[k], delta):
            self._after_structure(select=k + delta)

    def _group_name(self, item: Node) -> str:
        n = item.child("class_name") if item is not None else None
        return (n.value if n is not None and n.value else "这个大分类") if item else ""

    def _after_structure(self, select: int | None = None, select_last: bool = False):
        self._invalidate()
        self._fill_cats()
        if select_last and self.cats.count():
            self.cats.setCurrentRow(self.cats.count() - 1)
        elif select is not None and 0 <= select < self.cats.count():
            self.cats.setCurrentRow(select)
        self._render()

    # ── 搜索命中数 ──
    def _cat_hits(self, key) -> int:
        if self.doc is None:
            return 0
        if self.grouped:
            return sum(1 for lf in self.doc.leaves
                       if self._group_of(lf.path.split(".")[0].split("[")[0]) == key
                       and self._match(lf))
        items = self.tree.root_items()
        if isinstance(key, int) and 0 <= key < len(items):
            return sum(1 for lf in self.tree.leaves_of(items[key]) if self._match(lf))
        return 0

    def _update_cat_counts(self):
        q = self.search.text().strip()
        for row in range(self.cats.count()):
            it = self.cats.item(row)
            key = it.data(Qt.UserRole)
            it.setData(Qt.UserRole + 1,
                       self._cat_hits(key) if q else (it.data(Qt.UserRole + 2) or 0))
        self.cats.viewport().update()

    # ── 状态行 ──
    def _dirty_lines(self) -> int:
        if self.doc is None:
            return 0
        a, b = self.snapshot, self.doc.lines
        if a == b:
            return 0
        import difflib
        n = 0
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag != "equal":
                n += max(i2 - i1, j2 - j1)
        return n

    def _update_info(self):
        if self.doc is None:
            self.info.setText("没有加载到文件")
            return
        txt = f"{len(self.doc.lines)} 行 · {len(self.doc.leaves)} 个可编辑项"
        d = self._dirty_lines()
        if d:
            txt += f"　·　未保存 {d} 处"
        self.info.setText(txt)

    def show_raw_text(self):
        from .dlg_raw import RawViewDialog
        dlg = RawViewDialog(self.path, self)
        dlg.exec()

    # ── 保存 / 还原 / 回滚 ──
    def _backups(self) -> list:
        if not self.path.exists():
            return []
        return sorted(self.path.parent.glob(self.path.name + ".bak-*"), reverse=True)

    def show_rollbacks(self):
        baks = self._backups()
        if not baks:
            _say(self, "没有备份", "这个文件还没有 .bak 备份；第一次点「保存」时才会生成。")
            return
        from PySide6.QtCore import QPoint

        menu = QMenu(self)
        for bak in baks[:20]:
            stamp = bak.name.rsplit(".bak-", 1)[-1]
            try:
                when = datetime.strptime(stamp, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                when = stamp
            size = f"{bak.stat().st_size / 1024:.1f} KB"
            act = menu.addAction(f"{when}　·　{size}")
            act.triggered.connect(lambda _=False, b=bak: self.restore_backup(b))
        menu.addSeparator()
        menu.addAction(f"共 {len(baks)} 份备份").setEnabled(False)
        menu.ensurePolished()
        menu.popup(self.btn_rollback.mapToGlobal(QPoint(0, 30)))
        self._rollback_menu = menu

    def restore_backup(self, bak):
        bak = Path(bak)
        if not bak.exists():
            _say(self, "文件没了", f"找不到备份：{bak}")
            return
        if not _confirm(self, "用这份备份覆盖当前文件？",
                        f"备份：{bak.name}\n\n"
                        "当前文件会先另存为 .rollback-时间戳，再被这份备份覆盖；"
                        "没保存的改动会丢。"):
            return
        try:
            keep = self.path.with_name(self.path.name + ".rollback-" +
                                       datetime.now().strftime("%Y%m%d%H%M%S"))
            if self.path.exists():
                shutil.copy2(self.path, keep)
            shutil.copy2(bak, self.path)
        except Exception as e:
            _warn(self, "回滚失败", str(e))
            return
        self.reload()
        _say(self, "已回滚",
             f"已恢复成 {bak.name}\n\n回滚前的文件存为：\n{keep.name}")

    def save(self):
        if self.doc is None:
            return
        if not self._dirty_lines():
            self.info.setText("没有改动。")
            return
        try:
            bak = self.doc.save(backup=True)
        except Exception as e:
            _warn(self, "备份或写入失败", str(e))
            return
        try:
            n, diffs = self.doc.diff(self.path.with_name(bak))
        except Exception:
            n, diffs = -1, []
        head = f"已写入 {self.path.name}"
        if n >= 0:
            body = (f"变化 {n} 行，其余逐字节一致。\n\n备份：{bak}\n\n"
                    + ("\n".join(diffs[:12]) if diffs else ""))
        else:
            body = f"备份：{bak}"
        self.reload()
        _say(self, head,
             body + "\n\n⚠️ 这里只改了源文件，站点还没变。\n"
                    "要生效请走：构建验证 → 本地预览确认 → 再发布。")

    def revert(self):
        if self.doc is None:
            return
        if not self._dirty_lines():
            self.info.setText("没有改动。")
            return
        if not _confirm(self, "确认", "放弃全部未保存的改动？"):
            return
        self.reload()

    # ── 换肤 ──
    def prepare_theme(self):
        """换肤前先把页面里的控件拆掉，省得 setStyleSheet 对着几千个部件重算。"""
        self._build_id += 1
        self.busy.done()
        self._jobs = []
        self._page = None
        for page in self.cache.values():
            try:
                page.setParent(None)
                page.deleteLater()
            except RuntimeError:
                pass
        self.cache.clear()
        while self.host_lay.count():
            item = self.host_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        # deleteLater 要等事件循环才真删；这里立刻清掉，
        # 否则换肤时 setStyleSheet 还得对着这堆控件重算样式。
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def apply_theme(self):
        self.setStyleSheet(self._qss())
        self.cats.viewport().update()
        self._render()
