"""主窗口：左侧导航（FA7 图标）+ 右侧页面栈。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMenu,
    QMainWindow, QPushButton, QStackedWidget, QStatusBar, QStyle,
    QStyledItemDelegate, QStyleOptionViewItem, QVBoxLayout, QWidget,
)

from .. import fa, paths, settings, theme
from ..paths import DATA_PAGES
from . import anim, icons
from .about import AboutDialog
from .dlg_about import SettingsDialog
from .page_home import HomePage
from .page_raw import RawPage
from .page_publish import PublishPage
from .page_status import StatusPage
from .page_write import WritePage
from .page_yaml import YamlPage

APP_NAME = "纳多狐狐的写作台"
ICON_PATH = Path(__file__).resolve().parent.parent.parent / "app.ico"


class NavDelegate(QStyledItemDelegate):
    """导航项：左边一个 FA7 图标，右边中文标题。

    图标是字体字符（app/fa.py 里的码点），所以必须单独指定字体来画 ——
    Qt 的 item text 没法在同一段里混两种字体。
    """

    ICONS = [
        fa.get("house"),      # 首页
        fa.get("pen"),        # 写文章
        fa.get("server"),     # 服务器状态
        fa.get("rocket"),     # 发布
        fa.get("palette"),    # 主题配置
        fa.get("id-card"),     # 关于页数据
        fa.get("laptop"),     # 装备
        fa.get("link"),       # 友链
        fa.get("images"),     # 相册
        fa.get("lightbulb"),  # 创造力
    ]

    def __init__(self, parent=None, icons_list=None, imported=None):
        super().__init__(parent)
        # 直接引用窗口那份列表：之后再加页面，图标也能跟上
        self.icons = icons_list if icons_list is not None else list(NavDelegate.ICONS)
        self.imported = imported if imported is not None else set()

    def paint(self, painter, option, index):
        """全部自绘。QSS 的 ::item:hover 在自定义 delegate 下不一定生效，
        这里直接把悬停/选中的圆角底色画出来，保证鼠标划过有反馈。"""
        p = theme.c()
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        pressed = bool(option.state & QStyle.State_Sunken)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        bg = None
        if selected:
            bg = QColor(p["select"] if pressed else p["accent_soft"])
        elif hovered:
            bg = QColor(p["select"] if pressed else p["chip"])
        if bg is not None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(r.adjusted(4, 3, -4, -3), 8, 8)

        color = QColor(p["ink"] if (selected or hovered) else p["ink2"])

        row = index.row()
        icon = self.icons[row] if 0 <= row < len(self.icons) else ""
        if icon:
            painter.setFont(theme.icon_font(11.5))
            painter.setPen(color)
            painter.drawText(QRect(r.left() + 14, r.top(), 26, r.height()),
                             Qt.AlignVCenter | Qt.AlignLeft, icon)

        name = index.data()
        right_pad = 54
        if name in self.imported:
            # 导入的页面右边挂个垃圾桶，点它就能移除
            painter.setFont(theme.icon_font(10.5))
            painter.setPen(QColor(p["bad"] if hovered else p["ink2"]))
            painter.drawText(QRect(r.right() - 36, r.top(), 24, r.height()),
                             Qt.AlignVCenter | Qt.AlignRight, fa.get("trash-can"))
            right_pad = 78

        painter.setFont(theme.ui_font(9.5, bold=selected))
        painter.setPen(color)
        painter.drawText(QRect(r.left() + 46, r.top(), r.width() - right_pad, r.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, name)
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(0, 44)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1420, 900)
        self.setMinimumSize(1080, 680)
        self.pages: list[QWidget] = []
        self._icons = list(NavDelegate.ICONS)
        self._imported: dict[str, dict] = {}
        self._imported_names: set[str] = set()
        self._build()

    # ── 界面 ──
    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        # 左侧导航
        side = QWidget()
        side.setObjectName("NavSide")     # 整条侧边栏同一个底色，避免出现横向断层
        side.setFixedWidth(196)
        side.setAutoFillBackground(True)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)

        brand = QWidget()
        brand.setObjectName("BrandRow")
        bh0 = QHBoxLayout(brand)
        bh0.setContentsMargins(16, 14, 12, 10)
        bh0.setSpacing(9)
        logo = QLabel()
        logo.setFixedSize(26, 26)
        self.brand_logo = logo
        self._sync_brand()
        logo.setObjectName("BrandLogo")
        bh0.addWidget(logo)
        brand_text = QLabel(APP_NAME)
        brand_text.setObjectName("BrandText")
        bh0.addWidget(brand_text)
        bh0.addStretch(1)
        sv.addWidget(brand)

        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setFrameShape(QFrame.NoFrame)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.setMouseTracking(True)      # hover 状态要用
        self.nav.setItemDelegate(
            NavDelegate(self.nav, self._icons, self._imported_names))
        self.nav.viewport().installEventFilter(self)
        sv.addWidget(self.nav, 1)

        # 底部圆形图标按钮：外观 / 设置 / 关于
        bottom = QWidget()
        bottom.setObjectName("NavBottom")
        bh = QHBoxLayout(bottom)
        bh.setContentsMargins(0, 6, 0, 12)
        bh.setSpacing(6)
        bh.addStretch(1)

        self.btn_theme = self._round_button(
            fa.get("palette"), "外观：点击或悬停选一套", self._show_theme_menu)
        self._theme_menu = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(320)
        self._hover_timer.timeout.connect(self._show_theme_menu)
        self.btn_theme.installEventFilter(self)
        self.btn_settings = self._round_button(
            fa.get("gear"), "设置", self._open_settings)
        self.btn_about = self._round_button(
            fa.get("circle-info"), "关于", self._open_about)
        self.btn_donate = self._round_button(
            fa.get("heart"), "赞赏与支持", self._open_donate)

        for b in (self.btn_theme, self.btn_settings, self.btn_about, self.btn_donate):
            bh.addWidget(b)
        bh.addStretch(1)
        sv.addWidget(bottom)

        row.addWidget(side)

        self.stack = QStackedWidget()
        row.addWidget(self.stack, 1)

        # 页面（顺序即导航顺序）
        self._sync_theme_button()

        self.home = HomePage(goto=self._goto, open_settings=self._open_settings,
                             open_post=self._open_post, new_post=self._new_post,
                             open_blog=self._open_blog_folder)
        self._add_page("首页", self.home)
        self._add_page("写文章", WritePage())
        self._add_page("服务器状态", StatusPage(open_settings=self._open_settings))
        self._add_page("发布", PublishPage(open_settings=self._open_settings))
        if paths.CONFIG_YML.exists():
            self._add_page("主题yml配置",
                           YamlPage("主题yml配置", paths.CONFIG_YML, grouped=True))
        else:
            self._add_page("主题yml配置",
                           self._missing_page(str(paths.CONFIG_YML)))
        for name, path in DATA_PAGES:
            # 别的主题没有这些 _data 文件：没有就不显示，别让程序起不来
            if not path.exists():
                continue
            self._add_page(name, YamlPage(name, path, grouped=False))
        # 自己加的 yml 页（设置里存着名字 / 文件 / 图标）
        for entry in settings.get_custom_pages():
            raw = entry.get("file", "")
            f = Path(raw)
            if not f.is_absolute():
                f = paths.DATA_DIR / raw
            if not f.exists():
                continue
            name = entry.get("name") or f.stem
            self._add_page(name, self._make_data_page(name, f, imported=True),
                           entry.get("icon"))
            self._imported[name] = entry
            self._imported_names.add(name)
        # 导航最后一行：不是页面，点它开新建对话框
        self._add_row_index = self.nav.count()
        add_item = QListWidgetItem("导入 yml 配置")
        add_item.setSizeHint(QSize(0, 44))
        self.nav.addItem(add_item)
        self._icons.append(fa.get("file-import") or fa.get("file-lines"))
        while len(self._icons) < self.nav.count():
            self._icons.append("")
        self._last_page_row = 0
        self.nav.setContextMenuPolicy(Qt.CustomContextMenu)
        self.nav.customContextMenuRequested.connect(self._nav_menu)

        # ── 全局状态栏：左边提示，右边放写文章页的四个开关 ──
        sb: QStatusBar = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.global_hint = QLabel("就绪")
        self.global_hint.setStyleSheet(f"background: transparent; color: {theme.c()['ink2']};")
        sb.addWidget(self.global_hint)

        # 当前页的一句话提示（放右边，写文章页时被四个开关挤掉也不影响）
        self.page_tip = QLabel("")
        self.page_tip.setStyleSheet(f"background: transparent; color: {theme.c()['ink2']};")
        sb.addPermanentWidget(self.page_tip)

        self.write_page = self.pages[1]
        # status_hint 走 addWidget（左对齐），只有开关栏用 addPermanentWidget（右对齐）
        sb.addWidget(self.write_page.status_hint)
        sb.addPermanentWidget(self.write_page.toggle_bar)

        self.apply_hidden_pages()
        self.nav.currentRowChanged.connect(self._on_nav)
        self.nav.setCurrentRow(0)

        # 给所有按钮接上点击水波纹
        anim.install_ripple_tree(self)

    def _add_page(self, name: str, widget: QWidget, icon: str | None = None):
        item = QListWidgetItem(name)
        item.setSizeHint(QSize(0, 44))
        row = getattr(self, "_add_row_index", None)
        if row is None:
            self.nav.addItem(item)          # 内置页：图标已按顺序排在 _icons 里
            if icon:
                self._icons.append(fa.get(icon, ""))
        else:
            self.nav.insertItem(row, item)  # 自定义页：插在「新增 yml 配置」上面
            self._icons.insert(row, fa.get(icon, "") if icon else "")
            self._add_row_index = row + 1
        self.stack.addWidget(widget)
        widget.title = name
        self.pages.append(widget)

    # ── 自定义 yml 页 ──
    def _missing_page(self, what: str) -> QWidget:
        """某类文件不存在时的占位页：说清楚缺什么、去哪补。"""
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(8)
        t = QLabel("没找到这个文件")
        t.setStyleSheet("font-size:16px; font-weight:600;")
        v.addWidget(t)
        p = QLabel(what)
        p.setObjectName("Dim")
        p.setWordWrap(True)
        v.addWidget(p)
        tip = QLabel(
            "这是安知鱼主题的文件。换成别的 Hexo 主题时，这个页面会缺席；"
            "可以在设置里改「主题配置」指向你要编辑的 yml，或用「导入 yml 配置」单独加一页。")
        tip.setWordWrap(True)
        tip.setObjectName("Dim")
        v.addWidget(tip)
        v.addStretch(1)
        box.title = "主题yml配置"
        return box

    def _make_data_page(self, name: str, path, imported: bool = False):
        """能按结构解出来就用 YAML 表单，解不出来（或空的）就原文照读。"""
        try:
            page = YamlPage(name, path, grouped=False, show_raw=imported)
            if page.doc is not None and not page.doc.leaves and path.stat().st_size > 0:
                page.deleteLater()
                return RawPage(name, path)
            return page
        except Exception:
            return RawPage(name, path)

    def _import_yaml_page(self):
        from PySide6.QtWidgets import QDialog

        from .dlg_import_yaml import ImportYamlDialog

        dlg = ImportYamlDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        path = dlg.path()
        name = dlg.page_name()
        icon = dlg.page_icon()
        # 同一个文件已经导入过，直接跳过去，别加重复页
        for entry in settings.get_custom_pages():
            same = Path(entry.get("file", ""))
            if same == path or (not same.is_absolute() and paths.DATA_DIR / same == path):
                for row in range(self.nav.count()):
                    if self.nav.item(row).text() == entry.get("name"):
                        self.nav.setCurrentRow(row)
                        return
        entry = {"name": name, "file": str(path), "icon": icon}
        settings.add_custom_page(entry)
        self._imported[name] = entry
        self._imported_names.add(name)
        page = self._make_data_page(name, path, imported=True)
        self._add_page(name, page, icon)
        self.nav.setCurrentRow(self.stack.count() - 1)

    @staticmethod
    def _round_qss(p) -> str:
        """圆形图标按钮的样式。

        必须写 padding: 0 / min-width: 0 —— qt-material 的 QPushButton 默认带
        padding: 6px 14px，34px 宽的圆里左右一扣只剩几像素，图标会被裁成一道缝。
        """
        # font-family 必须写在 QSS 里：全局 QSS 的 QWidget { font-family: 思源黑体 }
        # 优先级高于 setFont()，会把按钮上的 Font Awesome 码点拿去用中文字体渲染，
        # 结果月亮变成 "("、齿轮变成 "←"。
        return (
            f"QPushButton {{ background: {p['chip']}; border: none;"
            f" border-radius: 17px; color: {p['ink2']};"
            f" padding: 0px; text-align: center;"
            f" font-family: '{theme.ICON_FAMILY}'; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {p['select']}; color: {p['ink']}; }}"
            f"QPushButton:pressed {{ background: {p['accent_soft']}; color: {p['ink']}; }}")

    def _round_button(self, icon: str, tip: str, slot) -> QPushButton:
        """34px 圆形图标按钮。"""
        p = theme.c()
        b = QPushButton(icon)
        b.setFixedSize(34, 34)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tip)
        b.setFont(theme.icon_font(11.5))
        b.setStyleSheet(self._round_qss(p))
        b.clicked.connect(slot)
        return b

    def _open_settings(self):
        dlg = SettingsDialog(self, on_theme=self.apply_theme_now)
        dlg.on_saved = self.apply_hidden_pages
        dlg.exec()
        self._sync_theme_button()

    def _open_about(self):
        AboutDialog(self).exec()

    def _on_nav(self, index: int):

        if index == getattr(self, "_add_row_index", -1):
            prev = getattr(self, "_last_page_row", 0)
            self.nav.setCurrentRow(prev)
            QTimer.singleShot(0, self._import_yaml_page)
            return
        if 0 <= index < self.stack.count():
            self._last_page_row = index
            self.stack.setCurrentIndex(index)
            w = self.stack.widget(index)
            name = getattr(w, "title", "")
            self.setWindowTitle(APP_NAME + (f" — {name}" if name else ""))
            anim.fade_in(w)

            if w is self.home:
                self.home.refresh()
            # 四个开关只在写文章页有意义，切走就藏起来
            is_write = (w is self.write_page)
            self.write_page.toggle_bar.setVisible(is_write)
            self.write_page.status_hint.setVisible(is_write)
            self.global_hint.setVisible(not is_write)
            if not is_write:
                self.global_hint.setText(f"{name}　·　就绪")
            self.page_tip.setText(getattr(w, "status_tip", "") if not is_write else "")

    # ── 换肤 ──
    def _sync_brand(self):
        pm = icons.fox_logo(26)
        if not pm.isNull():
            self.brand_logo.setPixmap(pm)

    def _sync_theme_button(self):
        self.btn_theme.setText(fa.get("palette"))
        pref = settings.get("theme") or "auto"
        cur = theme.theme_name()
        label = f"跟随系统（{cur}）" if pref == "auto" else cur
        self.btn_theme.setToolTip(f"外观：{label}　·　点击或悬停切换")

    def _hit_trash(self, pos):
        """鼠标是不是点在某个导入页右边的垃圾桶上。"""
        index = self.nav.indexAt(pos)
        if not index.isValid():
            return None
        name = index.data()
        if name not in self._imported_names:
            return None
        if pos.x() >= self.nav.viewport().width() - 40:
            return name
        return None

    def eventFilter(self, obj, event):
        nav = getattr(self, "nav", None)
        if nav is not None:
            try:
                is_viewport = obj is nav.viewport()
            except RuntimeError:
                is_viewport = False
            if is_viewport and event.type() == QEvent.MouseButtonRelease \
                    and event.button() == Qt.LeftButton:
                name = self._hit_trash(event.pos())
                if name:
                    QTimer.singleShot(0, lambda n=name: self._remove_imported(n))
                    return True
        btn = getattr(self, "btn_theme", None)
        if btn is not None and obj is btn:
            if event.type() == QEvent.Enter:
                self._hover_timer.start()
            elif event.type() == QEvent.Leave:
                self._hover_timer.stop()
        return super().eventFilter(obj, event)

    def _show_theme_menu(self):
        """调色盘按钮：深色 / 浅色 两个二级菜单，勾选当前那套。"""
        menu = QMenu(self)
        auto = menu.addAction("跟随系统")
        auto.setCheckable(True)
        auto.setChecked(theme.theme_id() in ("dark-black", "light-cool")
                        and settings.get("theme") in ("", "auto"))
        auto.triggered.connect(lambda _=False: self._set_theme("auto"))
        menu.addSeparator()
        groups = [("深色", ["dark-blue", "dark-black"]),
                  ("浅色", ["light-cool", "light-beige"])]
        for title, ids in groups:
            sub = menu.addMenu(title)
            for tid in ids:
                act = sub.addAction(theme.theme_name(tid))
                act.setCheckable(True)
                act.setChecked(tid == theme.theme_id())
                act.triggered.connect(lambda _=False, t=tid: self._set_theme(t))
        menu.ensurePolished()
        pos = self.btn_theme.mapToGlobal(QPoint(0, -menu.sizeHint().height() - 6))
        menu.popup(pos)
        self._theme_menu = menu

    def apply_theme_now(self, *_):
        """把当前 theme 里的配色刷到整个界面（设置里改外观也会走这里）。

        先把 YAML 页里那堆控件拆掉再换样式：setStyleSheet 会对每个部件重新算一遍
        样式，几千个控件一起算要十几秒。拆完只剩百来个，换肤就是秒级。
        """
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for page in self.pages:
                fn = getattr(page, "prepare_theme", None)
                if callable(fn):
                    fn()
            theme.apply(QApplication.instance(), theme.theme_id())
        finally:
            QApplication.restoreOverrideCursor()
        self._sync_brand()
        self._sync_theme_button()
        p = theme.c()
        for b in (self.btn_theme, self.btn_settings, self.btn_about, self.btn_donate):
            b.setStyleSheet(self._round_qss(p))
        for page in self.pages:
            fn = getattr(page, "apply_theme", None)
            if callable(fn):
                fn()
        p2 = theme.c()
        self.global_hint.setStyleSheet(
            f"background: transparent; color: {p2['ink2']};")
        self.page_tip.setStyleSheet(
            f"background: transparent; color: {p2['ink2']};")
        self.nav.viewport().update()      # 自定义 delegate 要手动重画

    def _set_theme(self, tid: str):
        settings.put("theme", tid)
        theme.use(theme.resolve(tid))
        self.apply_theme_now()

    def _toggle_theme(self):
        """保留给测试/快捷键：按顺序换下一套。"""
        self._set_theme(theme.next_theme())

    def _open_blog_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.BLOG)))

    def _open_post(self, path):
        self._goto("写文章")
        wp = self.write_page
        target = next((a for a in wp.articles if a.path == path), None)
        if target is None:
            wp.reload()
            target = next((a for a in wp.articles if a.path == path), None)
        if target is None:
            return
        wp.list.setCurrentRow(wp.articles.index(target))

    def _new_post(self):
        self._goto("写文章")
        self.write_page.new_article()

    # ── 导入页的右键菜单：只能移除导入的 ──
    def _nav_menu(self, pos):
        item = self.nav.itemAt(pos)
        if item is None:
            return
        name = item.text()
        if name not in self._imported:
            return
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        act = menu.addAction(f"移除导入页「{name}」")
        act.triggered.connect(lambda _=False, n=name: self._remove_imported(n))
        menu.exec(self.nav.mapToGlobal(pos))

    def _remove_imported(self, name: str):
        from PySide6.QtWidgets import QMessageBox
        entry = self._imported.get(name)
        if not entry:
            return
        import os
        if os.environ.get("ND_SILENT") != "1":
            if QMessageBox.question(
                    self, "移除导入页",
                    f"从导航里移除「{name}」？\n\n只移除这一页，不改动 yml 文件。") != QMessageBox.Yes:
                return
        row = next((i for i in range(self.nav.count())
                    if self.nav.item(i).text() == name), -1)
        if row < 0:
            return
        page = self.stack.widget(row) if 0 <= row < self.stack.count() else None
        # 删的时候别让选中行跳到最后那行「导入」，否则会立刻又弹一次导入框
        self.nav.blockSignals(True)
        try:
            self.nav.takeItem(row)
        finally:
            self.nav.blockSignals(False)
        if page is not None:
            self.stack.removeWidget(page)
            page.deleteLater()
            self.pages = [p for p in self.pages if p is not page]
        if 0 <= row < len(self._icons):
            self._icons.pop(row)
        if row < self._add_row_index:
            self._add_row_index -= 1

        # 选到相邻的页面（不要落到最后那行「导入」）
        if self.stack.count():
            self.nav.setCurrentRow(max(0, min(row - 1, self.stack.count() - 1)))
        else:
            self.nav.setCurrentRow(0)
        settings.set_custom_pages(
            [e for e in settings.get_custom_pages() if e.get("file") != entry.get("file")])
        self._imported.pop(name, None)
        self._imported_names.discard(name)

    def apply_hidden_pages(self):
        """按设置把「装备 / 相册 / 技能」这些入口藏起来（页面本身还在）。"""
        hidden = set(settings.get_hidden_pages())
        for i in range(self.nav.count()):
            item = self.nav.item(i)
            if item.text() == "导入 yml 配置":
                continue
            item.setHidden(item.text() in hidden)
        cur = self.nav.currentItem()
        if cur is not None and cur.isHidden():
            self.nav.setCurrentRow(0)

    def _open_donate(self):
        from .dlg_donate import DonateDialog
        DonateDialog(self).exec()

    def _goto(self, title: str):
        for row in range(self.nav.count()):
            if self.nav.item(row).text() == title:
                self.nav.setCurrentRow(row)
                return
