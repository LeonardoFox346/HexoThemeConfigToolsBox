"""写文章页：文章列表 | Markdown 编辑器 | 预览。

预览是两档的：
  · 轻量参考（QTextBrowser.setMarkdown）—— 快，但对内联 HTML 支持差；
  · 样式预览（QWebEngineView + 主题 index.css）—— 慢一点点，但能正确显示
    文章里预置的 HTML / <style> / <details>，接近站点最终效果。
样式预览用的浏览器是懒加载的：不打开开关就永远不创建，不占内存。
"""
from __future__ import annotations

import re

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QSizePolicy, QSplitter, QStackedWidget, QTextBrowser, QToolButton,
    QVBoxLayout, QWidget,
)

from .. import article as art
from .. import md_render, settings, theme
from .. import paths
from ..paths import CATEGORIES
from . import icons, md_menu
from .dlg_new import NewArticleDialog
from .md_editor import MdEditor
from .md_highlight import MarkdownHighlighter


class InfoDialog(QDialog):
    """文章信息弹窗。

    非模态：开着它也能继续看/改文章，窗口可以拖到一边。
    改这里只动 Front Matter 里对应的那几行，正文和其它字段一字不动。
    """

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("文章信息")
        self.setModal(False)                       # 非模态，可以边看边改
        self.setMinimumWidth(660)
        self._loading = False
        self._build()

    def _build(self):
        p = theme.c()
        self.setStyleSheet(f"QDialog {{ background: {p['surface']}; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(9)

        self.ed_title = QLineEdit()
        self.ed_title.setPlaceholderText("文章标题")
        self.ed_date = QLineEdit()
        self.ed_date.setPlaceholderText("2026-10-25 12:00:00")

        self.cb_cat = QComboBox()
        self.cb_cat.addItems(CATEGORIES)

        self.ed_tags = QLineEdit()
        self.ed_tags.setPlaceholderText("用逗号分隔，例如：安全, 运维")

        self.ed_cover = QLineEdit()
        self.ed_cover.setPlaceholderText("封面图地址，可留空")
        self.ed_desc = QLineEdit()
        self.ed_desc.setPlaceholderText("简介，会显示在首页卡片上")

        self.cb_cright = QComboBox()
        self.cb_cright.addItems(["type1", "type2", "type3", "type4", "type5", "关闭"])
        self.cb_cright.setToolTip(
            "写进 Front Matter 的 copyright.type。主题实际只区分 type1 和 type2。")

        self.ed_author = QLineEdit()
        self.ed_author.setPlaceholderText("留空用站点默认作者")

        g.addWidget(QLabel("标题"), 0, 0)
        g.addWidget(self.ed_title, 0, 1)
        g.addWidget(QLabel("日期"), 0, 2)
        g.addWidget(self.ed_date, 0, 3)

        g.addWidget(QLabel("分类"), 1, 0)
        g.addWidget(self.cb_cat, 1, 1)
        g.addWidget(QLabel("标签"), 1, 2)
        g.addWidget(self.ed_tags, 1, 3)

        g.addWidget(QLabel("封面"), 2, 0)
        g.addWidget(self.ed_cover, 2, 1)
        g.addWidget(QLabel("简介"), 2, 2)
        g.addWidget(self.ed_desc, 2, 3)

        g.addWidget(QLabel("版权"), 3, 0)
        g.addWidget(self.cb_cright, 3, 1)
        g.addWidget(QLabel("作者"), 3, 2)
        g.addWidget(self.ed_author, 3, 3)

        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)
        outer.addLayout(g)

        tip = QLabel("改完直接生效（写进内存里的 Front Matter），点「保存」才落盘。")
        tip.setStyleSheet(f"color: {p['ink2']}; font-size: 11px; background: transparent;")
        outer.addWidget(tip)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText("关闭")
        bb.rejected.connect(self.close)
        bb.accepted.connect(self.close)
        outer.addWidget(bb)

        for w in (self.ed_title, self.ed_date, self.ed_tags,
                  self.ed_cover, self.ed_desc, self.ed_author):
            w.editingFinished.connect(self._emit)
        self.cb_cat.currentTextChanged.connect(lambda _=0: self._emit())
        self.cb_cright.currentTextChanged.connect(lambda _=0: self._emit())

    def _emit(self):
        if not self._loading:
            self.changed.emit()

    # ── 读 / 写 ──
    def load(self, a):
        self._loading = True
        try:
            self.ed_title.setText(a.title)
            self.ed_date.setText(a.date)

            cat = a.categories[0] if a.categories else ""
            i = self.cb_cat.findText(cat)
            if i < 0 and cat:
                self.cb_cat.addItem(cat)
                i = self.cb_cat.count() - 1
            self.cb_cat.setCurrentIndex(max(0, i))

            self.ed_tags.setText("、".join(a.tags))
            self.ed_cover.setText(a.cover)

            desc = a.fm.get("description", "")
            self.ed_desc.setText("" if isinstance(desc, list) else str(desc))

            ct = a.fm_get_nested("copyright", "type")
            if not ct or self.cb_cright.findText(ct) < 0:
                ct = "关闭"
            self.cb_cright.setCurrentText(ct)

            author = a.fm.get("author", "")
            self.ed_author.setText("" if isinstance(author, list) else str(author))

            self.setWindowTitle(f"文章信息 — {a.title}")
        finally:
            self._loading = False

    def apply(self, a) -> bool:
        """把弹窗内容写回 Front Matter。返回是否真的有改动。"""
        if self._loading or a is None:
            return False
        before = list(a.fm_lines)

        title = self.ed_title.text().strip()
        if title and title != a.title:
            a.fm_set("title", title)

        date = self.ed_date.text().strip()
        if date and date != a.date:
            a.fm_set("date", date)

        cat = self.cb_cat.currentText().strip()
        if cat and (not a.categories or a.categories[0] != cat):
            a.fm_set_list("categories", [cat])

        tags = [x.strip() for x in re.split(r"[,，、]", self.ed_tags.text()) if x.strip()]
        if tags != a.tags:
            a.fm_set_list("tags", tags)

        cover = self.ed_cover.text().strip()
        if cover != a.cover:
            a.fm_set("cover", cover)

        desc = self.ed_desc.text().strip()
        cur_desc = a.fm.get("description", "")
        if not isinstance(cur_desc, list) and desc != str(cur_desc).strip():
            if desc:
                a.fm_set("description", desc)
            elif "description" in a.fm:
                a.fm_set("description", "")

        ct = self.cb_cright.currentText()
        if ct.startswith("type"):
            if a.fm_get_nested("copyright", "type") != ct:
                a.fm_set_nested("copyright", "type", ct)
        else:
            if "copyright" in a.fm:
                cur = str(a.fm.get("copyright", ""))
                if cur.lower() != "false":
                    a.fm_set("copyright", "false")

        author = self.ed_author.text().strip()
        cur_author = a.fm.get("author", "")
        if not isinstance(cur_author, list) and author != str(cur_author).strip():
            if author:
                a.fm_set("author", author)
            elif "author" in a.fm:
                a.fm_set("author", "")

        return a.fm_lines != before


class WritePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title = "写文章"
        self.status_tip = "右键可插入 Markdown 格式　·　点保存才写盘"
        self.articles: list[art.Article] = []
        self.cur: art.Article | None = None
        self.preview_web = None            # 懒加载，不用就不创建
        self.info_dlg = None               # 文章信息弹窗，用到才建
        self._syncing = False
        self._loading = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(280)
        self._timer.timeout.connect(self.refresh_preview)
        self._build()
        self.reload()

    # ══════════════ 界面 ══════════════
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 顶栏 ──
        bar = QWidget()
        bar.setFixedHeight(40)          # 28px 按钮 + 上下留白，别让布局压掉按钮底边
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 5, 12, 5)
        h.setSpacing(0)

        def tool_btn(text, icon_name, primary=False, tip=""):
            b = QPushButton(text)
            b.setObjectName("ToolBtnPrimary" if primary else "ToolBtn")
            # 主按钮是蓝底，图标必须用白色；其余用正文色，别用 ink2（太暗看不清）
            color = "#FFFFFF" if primary else theme.c()["ink"]
            b.setIcon(icons.fa_icon(icon_name, 16, color=color))
            b.setIconSize(QSize(14, 14))
            b.setFixedHeight(28)
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)   # 不被布局压缩
            b.setCursor(Qt.PointingHandCursor)
            if tip:
                b.setToolTip(tip)
            return b

        # 左侧按钮区固定 300px；右侧放一个同样 300px 的空壳。
        # 左右等宽，中间那格就正好在窗口正中，标题才是真居中。
        SIDE = 360

        left_box = QWidget()
        left_box.setFixedWidth(SIDE)
        lb = QHBoxLayout(left_box)
        lb.setContentsMargins(0, 0, 0, 0)
        lb.setSpacing(6)

        self.btn_new = tool_btn("新建", "circle-plus", True, "新建一篇文章")
        self.btn_new.clicked.connect(self.new_article)
        lb.addWidget(self.btn_new)
        self.btn_save = tool_btn("保存", "floppy-disk", False, "写回磁盘（会先备份 .bak）")
        self.btn_save.clicked.connect(self.save)
        lb.addWidget(self.btn_save)
        self.btn_reload = tool_btn("重扫", "arrows-rotate", False, "重新扫描 _posts 目录")
        self.btn_reload.clicked.connect(self.reload)
        lb.addWidget(self.btn_reload)
        self.btn_info = tool_btn("信息", "circle-info", False, "打开文章信息（可拖动的小窗口）")
        self.btn_info.clicked.connect(self._open_info)
        lb.addWidget(self.btn_info)
        lb.addStretch(1)
        h.addWidget(left_box)

        # 中间标题
        mid_box = QWidget()
        mb = QHBoxLayout(mid_box)
        mb.setContentsMargins(0, 0, 0, 0)
        mb.setSpacing(8)
        mb.addStretch(1)

        self.lbl_cur = QLabel("")
        self.lbl_cur.setStyleSheet(
            f"color: {theme.c()['ink']}; font-size: 19px; font-weight: 700;"
            f" background: transparent;")
        mb.addWidget(self.lbl_cur)

        self.lbl_file = QLabel("")
        self.lbl_file.setStyleSheet(
            f"color: {theme.c()['ink2']}; font-size: 13px; background: transparent;")
        mb.addWidget(self.lbl_file)
        mb.addStretch(1)
        h.addWidget(mid_box, 1)

        right_box = QWidget()
        right_box.setFixedWidth(SIDE)
        h.addWidget(right_box)

        root.addWidget(bar)

        # ── 三栏 ──
        self.split = QSplitter(Qt.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.split.setHandleWidth(2)      # 分隔条细一点

        # 左：文章列表
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 4, 8)
        lv.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索标题")
        self.search.textChanged.connect(self._fill_list)
        lv.addWidget(self.search)
        self.list = QListWidget()
        self.list.setUniformItemSizes(True)
        self.list.setWordWrap(False)
        self.list.setTextElideMode(Qt.ElideRight)
        self.list.currentRowChanged.connect(self._on_pick)
        lv.addWidget(self.list, 1)
        self.split.addWidget(left)

        # 中：编辑器
        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(4, 8, 4, 8)
        mv.setSpacing(6)
        self.editor = MdEditor()
        self.editor.setPlaceholderText("在这里写正文……　右键可以插入常用格式")
        f = QFont("JetBrains Mono", 10)
        f.setStyleHint(QFont.Monospace)
        self.editor.setFont(f)
        self.editor.setTabStopDistance(28)
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self._editor_menu)
        self.hl = MarkdownHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._on_text)
        self.editor.verticalScrollBar().valueChanged.connect(self._sync_scroll)
        mv.addWidget(self.editor, 1)
        self.split.addWidget(mid)

        # 右：预览（两档）
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(4, 8, 8, 8)
        rv.setSpacing(6)

        self.preview_stack = QStackedWidget()

        self.preview_light = QTextBrowser()
        self.preview_light.setOpenExternalLinks(True)
        self.preview_light.setContextMenuPolicy(Qt.CustomContextMenu)
        self.preview_light.customContextMenuRequested.connect(self._preview_menu)
        self.preview_stack.addWidget(self.preview_light)

        rv.addWidget(self.preview_stack, 1)
        self.split.addWidget(right)

        self.split.setSizes([300, 620, 520])
        root.addWidget(self.split, 1)

        # ── 状态栏控件：不自己建一条，交给主窗口的 QStatusBar 统一放 ──
        self.status_hint = QLabel("就绪")
        # background: transparent 必须写 —— 全局 QSS 的 QWidget{background:bg}
        # 会给它涂一块比状态栏更深的底色，看起来像贴了个色块
        self.status_hint.setStyleSheet(
            f"color: {theme.c()['ink2']}; background: transparent;")

        self.toggle_bar = QWidget()
        tb = QHBoxLayout(self.toggle_bar)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(6)

        # 默认值从设置读（设置里也能改）；同步滚动默认开
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
            self._web_ok = True
        except Exception:
            self._web_ok = False

        self.tg_preview = self._toggle_btn(
            "eye", "同步预览：编辑时实时刷新右边预览", settings.get("ed_preview") != "0")
        if self._web_ok:
            self.tg_style = self._toggle_btn(
                "globe",
                "样式预览：用内置浏览器套主题样式渲染，能显示文章里的 HTML（第一次打开会慢一两秒）",
                settings.get("ed_style") == "1")
        else:
            self.tg_style = self._toggle_btn(
                "globe", "样式预览需要 WebEngine 组件，当前精简版未内置", False)
            self.tg_style.setEnabled(False)
        self.tg_immersive = self._toggle_btn(
            "expand", "沉浸：只看正文，藏起列表和预览",
            settings.get("ed_immersive") == "1")
        self.tg_sync = self._toggle_btn(
            "arrows-up-down", "同步滚动：编辑器滚动时预览按比例跟随",
            settings.get("ed_sync") != "0")
        for btn, key in ((self.tg_preview, "ed_preview"), (self.tg_style, "ed_style"),
                         (self.tg_immersive, "ed_immersive"), (self.tg_sync, "ed_sync")):
            btn.toggled.connect(lambda on, k=key: settings.put(k, "1" if on else "0"))
        for w in (self.tg_preview, self.tg_style, self.tg_immersive, self.tg_sync):
            tb.addWidget(w)

        self.tg_preview.toggled.connect(lambda _=0: self.refresh_preview())
        self.tg_style.toggled.connect(lambda _=0: self.refresh_preview())
        self.tg_immersive.toggled.connect(self._toggle_immersive)

    # ══════════════ 文章列表 ══════════════
    def reload(self):
        self.articles = art.scan()
        self._fill_list()

    def _fill_list(self):
        kw = self.search.text().strip().lower()
        self.list.blockSignals(True)
        self.list.clear()
        shown = 0
        for a in self.articles:
            if kw and kw not in a.title.lower() and kw not in a.path.name.lower():
                continue
            item = QListWidgetItem(f"{a.date[:10]}  {a.title}")
            item.setToolTip(f"{a.title}\n{a.path}")
            item.setSizeHint(QSize(0, 34))
            self.list.addItem(item)
            item.setData(Qt.UserRole, a)
            shown += 1
        self.list.blockSignals(False)
        self.status_hint.setText(f"{len(self.articles)} 篇文章" + (f"（筛出 {shown}）" if kw else ""))
        # 进入页面不自动打开文章：即使有文章也保持空白，等用户自己点
        if self.cur is None:
            self.refresh_preview()

    def _on_pick(self, row: int):
        if row < 0:
            return
        item = self.list.item(row)
        if item is None:
            return
        a = item.data(Qt.UserRole)
        if a is not None:
            self.open(a)

    def open(self, a: art.Article):
        if self.cur is not None and self.cur.body_dirty:
            r = QMessageBox.question(
                self, "未保存", f"《{self.cur.title}》有未保存的改动，先保存吗？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Save:
                self.save()
            elif r == QMessageBox.Cancel:
                return
        self.cur = a
        self._loading = True
        self.editor.setPlainText(a.body)
        self._loading = False
        if self.info_dlg is not None and self.info_dlg.isVisible():
            self.info_dlg.load(a)
        self.lbl_cur.setText(a.title)
        self.lbl_file.setText(a.path.name)
        self.refresh_preview()
        w = self.window()
        if w:
            w.setWindowTitle(f"纳多狐狐的写作台 — 写文章 — {a.title}")

    # ══════════════ 编辑 ══════════════
    def _on_text(self):
        if self._loading or self.cur is None:
            return
        self.cur.body = self.editor.toPlainText()
        self.cur.body_dirty = True
        self._update_info()
        if self.tg_preview.isChecked():
            self._timer.start()

    def _open_info(self):
        """打开文章信息弹窗（非模态，可以拖到一边对着文章改）。"""
        if self.cur is None:
            self.status_hint.setText("先选一篇文章")
            return
        if self.info_dlg is None:
            self.info_dlg = InfoDialog(self)
            self.info_dlg.changed.connect(self._on_info_changed)
        self.info_dlg.load(self.cur)
        self.info_dlg.show()
        self.info_dlg.raise_()
        self.info_dlg.activateWindow()

    def _on_info_changed(self):
        """文章信息面板改了什么 → 写回 Front Matter。"""
        if self.cur is None:
            return
        if self.info_dlg is not None and self.info_dlg.apply(self.cur):
            self.cur.body_dirty = True
            self._update_info()

    def _update_info(self):
        if self.cur is None:
            return
        star = " · 未保存" if self.cur.body_dirty else ""
        self.status_hint.setText(
            f"{len(self.articles)} 篇文章　·　当前 {self.cur.word_count} 字{star}")

    # ══════════════ 预览 ══════════════
    def _ensure_web(self):
        """第一次打开样式预览时才创建浏览器。"""
        if self.preview_web is None:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            self.preview_web = QWebEngineView()
            self.preview_web.setContextMenuPolicy(Qt.DefaultContextMenu)
            self.preview_stack.addWidget(self.preview_web)
        return self.preview_web

    def refresh_preview(self):
        if self.cur is None:
            self.preview_stack.setCurrentWidget(self.preview_light)
            self.preview_light.setMarkdown("")
            # 没打开文章时整块预览都收起来，别留一大片空白
            self.preview_stack.setVisible(False)
            return
        self.preview_stack.setVisible(True)

        text = self.editor.toPlainText()

        if self.tg_style.isChecked() and self._web_ok:
            web = self._ensure_web()
            self.preview_stack.setCurrentWidget(web)
            # 主题 CSS 是站点样式，按亮色渲染才看得清（站点默认也是亮色）
            html = md_render.page(text, use_theme_css=True, dark=False)
            web.setHtml(html, QUrl.fromLocalFile(str(paths.BLOG)))
        else:
            self.preview_stack.setCurrentWidget(self.preview_light)
            self.preview_light.setMarkdown(text)

    # ══════════════ 右键菜单 ══════════════
    def _editor_menu(self, pos):
        m = md_menu.build(self.editor, self)
        m.exec(self.editor.mapToGlobal(pos))

    def _preview_menu(self, pos):
        """预览里右键：定位到此段。"""
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        act = m.addAction("定位到此段")
        m.addSeparator()
        m.addAction("复制选中文字", lambda: self.preview_light.copy())
        r = m.exec(self.preview_light.mapToGlobal(pos))
        if r is act:
            self._locate_source(pos)

    def _locate_source(self, pos):
        """把预览里点到的那一段，回到 Markdown 源码里定位。"""
        cur = self.preview_light.cursorForPosition(pos)
        block = cur.block()
        text = block.text().strip()
        if not text:
            return
        # 取一段够长的特征串去源码里找
        needle = re.sub(r"\s+", "", text)[:24]
        if not needle:
            return
        src = self.editor.toPlainText()
        src_flat = re.sub(r"\s+", "", src)
        idx = src_flat.find(needle)
        if idx < 0:
            needle = needle[:12]
            if not needle:
                return
            idx = src_flat.find(needle)
        if idx < 0:
            self.status_hint.setText("没在源码里找到这一段")
            return
        # 把「去掉空白后的下标」映射回原文位置
        pos_src, count = 0, 0
        while pos_src < len(src) and count < idx:
            if not src[pos_src].isspace():
                count += 1
            pos_src += 1
        c = self.editor.textCursor()
        c.setPosition(min(pos_src, len(src)))
        c.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        self.editor.setTextCursor(c)
        self.editor.centerCursor()
        self.editor.setFocus()
        self.status_hint.setText("已定位到源码对应行")

    # ══════════════ 模式 ══════════════
    def _toggle_btn(self, icon: str, tip: str, checked: bool) -> QPushButton:
        """状态栏上的小开关。用 QIcon（pixmap）而不是字体字符 ——
        这样不受全局 QSS 的 font-family 影响，颜色也能自己控制。"""
        b = QPushButton()
        b.setCheckable(True)
        b.setChecked(checked)
        b.setFixedSize(28, 26)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tip)
        b.setIconSize(QSize(14, 14))
        b._fa_name = icon
        b.toggled.connect(lambda _=False: self._style_toggle(b))
        self._style_toggle(b)
        return b

    def _style_toggle(self, b):
        p = theme.c()
        on = b.isChecked()
        b.setIcon(icons.fa_icon(b._fa_name, 14, active=on))
        b.setStyleSheet(
            f"QPushButton {{ border-radius: 6px; padding: 0px;"
            f" background: {p['accent_soft'] if on else 'transparent'};"
            f" border: 1px solid {p['accent'] if on else 'transparent'}; }}"
            f"QPushButton:hover {{ background: {p['chip'] if not on else p['select']}; }}")

    def _sync_scroll(self, value: int):
        """编辑器滚动 → 预览按比例滚。两档预览分别处理。"""
        if not getattr(self, "tg_sync", None) or not self.tg_sync.isChecked():
            return
        if self.cur is None or self._syncing:
            return
        self._syncing = True
        try:
            sb = self.editor.verticalScrollBar()
            ratio = (value / sb.maximum()) if sb.maximum() > 0 else 0.0
            if self.tg_style.isChecked() and self.preview_web is not None:
                self.preview_web.page().runJavaScript(
                    "window.scrollTo(0, %.4f * (document.body.scrollHeight - window.innerHeight));" % ratio)
            else:
                pb = self.preview_light.verticalScrollBar()
                pb.setValue(int(ratio * pb.maximum()))
        finally:
            self._syncing = False

    def _toggle_immersive(self, state):
        on = bool(state)
        self.split.widget(0).setVisible(not on)     # 文章列表
        self.split.widget(2).setVisible(not on)     # 预览
        if not on:
            self.split.setSizes([300, 620, 520])
        self.editor.setFocus()

    # ══════════════ 新建 / 保存 ══════════════
    def new_article(self):
        dlg = NewArticleDialog(self)
        if dlg.exec() != NewArticleDialog.Accepted:
            return
        v = dlg.values()
        a = art.create(
            v["title"], category=v["category"], tags=v["tags"], cover=v["cover"],
            date=v["date"], description=v["description"], copyright=v["copyright"],
            author=v["author"],
        )
        self.articles.insert(0, a)
        self.cur = None
        self._fill_list()
        self.list.setCurrentRow(0)
        self.open(a)
        self.editor.setFocus()

    def save(self):
        if self.cur is None:
            QMessageBox.information(self, "提示", "先选一篇文章。")
            return
        try:
            self.cur.body = self.editor.toPlainText()
            self.cur.path.parent.mkdir(parents=True, exist_ok=True)
            self.cur.save()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self.reload()
        self._update_info()
        QMessageBox.information(
            self, "已保存",
            f"已写入 {self.cur.path.name}\n\n"
            "⚠️ 只改了源文件，站点还没变。\n"
            "要生效请走：发布页构建 → 本地预览确认 → 再发布。")

    # ══════════════ 换肤 ══════════════
    def apply_theme(self):
        self.hl.rebuild()
        self.hl.rehighlight()
        if hasattr(self.editor, "apply_theme"):
            self.editor.apply_theme()
        self.status_hint.setStyleSheet(
            f"color: {theme.c()['ink2']}; background: transparent;")
        if hasattr(self, "lbl_cur"):
            self.lbl_cur.setStyleSheet(
                f"color: {theme.c()['ink']}; font-size: 14px; font-weight: 700;"
                f" background: transparent;")
            self.lbl_file.setStyleSheet(
                f"color: {theme.c()['ink2']}; font-size: 11px; background: transparent;")
        if self.preview_web is not None and self.tg_style.isChecked():
            self.refresh_preview()
