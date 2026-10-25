"""MD2 风格配色与全局 QSS。

四套外观：深色（蓝调）/ 深色（黑）/ 浅色（冷白）/ 浅色（米黄）。
换肤只改配色表，QSS 是同一份模板。"""

# ── 深色 ──
DARK = dict(
    bg="#12161C",
    surface="#171C24",
    panel="#1B222C",
    field="#0F141A",
    ink="#E6EAF0",
    ink2="#93A0B1",
    line="#262F3B",
    accent="#5B9DFF",
    accent_soft="#22375C",
    good="#4ADE80",
    warn="#FBBF24",
    bad="#F87171",
    chip="#202834",
    select="#2A4A78",
)

# ── 浅色 ──
LIGHT = dict(
    bg="#F4F6FA",
    surface="#FFFFFF",
    panel="#EDF1F6",
    field="#FFFFFF",
    ink="#1B2430",
    ink2="#5E6B7C",
    line="#DCE2EA",
    accent="#1A73E8",
    accent_soft="#D8E7FF",
    good="#15803D",
    warn="#B45309",
    bad="#DC2626",
    chip="#E8EEF6",
    select="#C7DCFB",
)

# ── 深色（黑）──
BLACK = dict(
    bg="#0A0A0B",
    surface="#16161A",
    panel="#1E1E23",
    field="#050506",
    ink="#EDEDF0",
    ink2="#A2A2AC",
    line="#34343B",
    accent="#6DA8FF",
    accent_soft="#22304A",
    good="#4ADE80",
    warn="#FBBF24",
    bad="#F87171",
    chip="#26262C",
    select="#2A3448",
)

# ── 浅色（米黄）──
BEIGE = dict(
    bg="#F5F0E4",
    surface="#FFFDF6",
    panel="#EDE6D6",
    field="#FFFFFF",
    ink="#25211A",
    ink2="#6E6656",
    line="#DFD5C1",
    accent="#A9702F",
    accent_soft="#F1E2CB",
    good="#3F7D3A",
    warn="#A16207",
    bad="#B4342B",
    chip="#EFE8D9",
    select="#E7D5B8",
)

# 顺序就是左下角按钮循环的顺序
PALETTES = {
    "dark-blue": ("深色（蓝调）", DARK),
    "dark-black": ("深色（黑）", BLACK),
    "light-cool": ("浅色（冷白）", LIGHT),
    "light-beige": ("浅色（米黄）", BEIGE),
}
THEME_ORDER = ["dark-blue", "dark-black", "light-cool", "light-beige"]

_current = DARK
_dark_mode = True
_current_id = "dark-blue"


def is_dark() -> bool:
    return _dark_mode


def c() -> dict:
    """当前配色表。"""
    return _current


def theme_id() -> str:
    return _current_id


def theme_name(which: str | None = None) -> str:
    return PALETTES.get(which or _current_id, ("深色（蓝调）", DARK))[0]


def system_dark() -> bool:
    """Windows 的「应用深色模式」开关。取不到就按深色算。"""
    try:
        import winreg
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        v, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
        return int(v) == 0
    except Exception:
        return True


def resolve(pref: str | None) -> str:
    """把设置里的外观偏好落成具体一套。auto = 跟随系统（深=黑，浅=白）。"""
    if not pref or pref == "auto":
        return "dark-black" if system_dark() else "light-cool"
    return pref if pref in PALETTES else "dark-blue"


def next_theme() -> str:
    k = THEME_ORDER.index(_current_id) if _current_id in THEME_ORDER else 0
    return THEME_ORDER[(k + 1) % len(THEME_ORDER)]


def use(which) -> dict:
    """切换配色。接受外观 id，也兼容老的 True/False（= 蓝调 / 冷白）。"""
    global _current, _dark_mode, _current_id
    if isinstance(which, bool):
        _current_id = "dark-blue" if which else "light-cool"
    elif which in PALETTES:
        _current_id = which
    _current = PALETTES[_current_id][1]
    _dark_mode = _current_id.startswith("dark")
    return _current


def qss() -> str:
    """整窗样式表。改动后重新 setStyleSheet 即可整体换肤。"""
    p = _current
    return f"""
    QWidget {{
        background: {p['bg']};
        color: {p['ink']};
        font-family: "{UI_FAMILY}", "Microsoft YaHei UI", "Segoe UI", sans-serif;
        font-size: 14px;
    }}
    QMainWindow, QDialog {{ background: {p['bg']}; }}

    /* ── 左侧导航 ── */
    QListWidget#Nav {{
        background: {p['panel']};
        border: none;
        outline: 0;
        padding: 8px 6px;
    }}
    /* 导航项的背景一律由 NavDelegate 自绘 —— 这里再画一遍会出现两套圆角错位 */
    QListWidget#Nav::item {{
        height: 44px;
        border: none;
        background: transparent;
        color: {p['ink2']};
    }}
    QListWidget#Nav::item:hover {{ background: transparent; }}
    QListWidget#Nav::item:selected {{ background: transparent; }}

    /* 侧边栏底板：nav / brand / 底部按钮统一坐在这一层上 */
    QWidget#NavSide {{ background: {p['panel']}; }}

    QWidget#NavBottom {{ background: {p["panel"]}; }}

    QLabel#Brand {{
        background: {p['panel']};
        color: {p['ink']};
        font-size: 15px;
        font-weight: 700;
        padding: 18px 0 10px 18px;
    }}
    QWidget#BrandRow {{ background: {p['panel']}; }}
    QLabel#BrandText {{
        background: {p['panel']};
        color: {p['ink']};
        font-size: 15px;
        font-weight: 700;
    }}
    QLabel#BrandLogo {{ background: {p['panel']}; }}

    /* ── 通用控件 ── */
    QPushButton {{
        background: {p['surface']};
        border: 1px solid {p['line']};
        border-radius: 7px;
        padding: 6px 14px;
        color: {p['ink']};
    }}
    QPushButton:hover {{ background: {p['chip']}; }}
    QPushButton:pressed {{ background: {p['select']}; }}
    QPushButton:disabled {{ color: {p['ink2']}; }}

    /* 顶栏那种小工具按钮：图标 + 文字，比默认矮一点 */
    QPushButton#ToolBtnPrimary {{
        background: {p['accent']};
        color: #FFFFFF;
        border: 1px solid {p['accent']};
        border-radius: 7px;
        padding: 0px 10px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#ToolBtnPrimary:hover {{ background: {p['select']}; }}
    QPushButton#ToolBtnPrimary:disabled {{ background: {p['line']}; border-color: {p['line']}; color: {p['ink2']}; }}

    QPushButton#ToolBtn {{
        padding: 0px 10px;
        font-size: 12px;
    }}

    QPushButton#Primary {{
        background: {p['accent']};
        border: 1px solid {p['accent']};
        color: #FFFFFF;
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{ background: {p['accent']}; }}
    QPushButton#Primary:disabled {{ background: {p['line']}; border-color: {p['line']}; color: {p['ink2']}; }}

    QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QSpinBox, QComboBox {{
        background: {p['field']};
        border: 1px solid {p['line']};
        border-radius: 6px;
        padding: 5px 8px;
        color: {p['ink']};
        selection-background-color: {p['accent']};
        selection-color: #FFFFFF;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {p['accent']}; }}

    /* ── 表格（YAML 编辑页的主控件，天生虚拟化）── */
    QTableView {{
        background: {p['surface']};
        alternate-background-color: {p['surface']};
        border: 1px solid {p['line']};
        border-radius: 8px;
        gridline-color: {p['line']};
        selection-background-color: {p['accent_soft']};
        selection-color: {p['ink']};
    }}
    QTableView::item {{ padding: 6px 10px; border: none; }}
    QTableView::item:selected {{ background: {p['accent_soft']}; color: {p['ink']}; }}
    QHeaderView::section {{
        background: {p['panel']};
        color: {p['ink2']};
        border: none;
        border-bottom: 1px solid {p['line']};
        padding: 7px 10px;
        font-weight: 600;
    }}
    QTableView QLineEdit {{ border: 1px solid {p['accent']}; border-radius: 4px; padding: 2px 4px; }}

    QTableCornerButton::section {{ background: {p['panel']}; border: none; }}

    /* ── 滚动条 ── */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{
        background: {p['line']}; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p['ink2']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {p['line']}; border-radius: 5px; min-width: 30px; }}

    /* ── 其它 ── */
    QSplitter::handle {{ background: {p['line']}; }}
    QSplitter::handle:hover {{ background: {p['accent']}; }}
    QTabWidget::pane {{ border: none; }}
    QGroupBox {{
        border: 1px solid {p['line']}; border-radius: 8px;
        margin-top: 12px; padding-top: 8px;
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {p['ink2']}; }}
    QCheckBox {{ spacing: 8px; }}
    QToolTip {{
        background: {p['panel']}; color: {p['ink']};
        border: 1px solid {p['line']}; border-radius: 6px; padding: 8px;
    }}
    QStatusBar {{ background: {p['panel']}; color: {p['ink2']}; border-top: 1px solid {p['line']}; }}
    /* 右键菜单：字号和行距压小，不然一屏放不下几项 */
    QMenu {{
        background: {p['surface']};
        border: 1px solid {p['line']};
        border-radius: 7px;
        padding: 3px;
        font-size: 11px;
    }}
    QMenu::item {{
        padding: 1px 12px 1px 2px;
        border-radius: 4px;
        min-height: 15px;
        margin: 0px;
    }}
    QMenu::item:selected {{ background: {p['accent_soft']}; color: {p['ink']}; }}
    QMenu::item:disabled {{ color: {p['ink2']}; }}
    QMenu::icon {{ padding-left: 3px; margin: 0px; width: 13px; }}
    QMenu::separator {{ height: 1px; background: {p['line']}; margin: 3px 6px; }}
    QMenu::right-arrow {{ width: 10px; height: 10px; margin-right: 2px; }}
    """


MONO_FAMILY = "JetBrains Mono, Consolas, Cascadia Mono, monospace"


# ══════════════ 字体 ══════════════
# 三套字体都从 fonts\ 目录加载，不依赖系统装没装：
#   Font Awesome 7 Free  → 图标（app/fa.py 里的码点就是这套字体的）
#   JetBrains Mono       → 代码 / 等宽
#   Noto Sans SC         → 中文正文（思源黑体）
from pathlib import Path as _Path

from .paths import APP_DIR as _APP_DIR

_FONT_DIR = _APP_DIR / "fonts"

UI_FAMILY = "Microsoft YaHei UI"      # 兜底：思源加载失败也不至于难看
MONO_FONT_FAMILY = "Consolas"
ICON_FAMILY = "Segoe UI Symbol"       # 兜底：图标字体没加载时至少不显示方块

_fonts_loaded = False
BUNDLED_UI = "Noto Sans CJK SC"        # 自带正文字体
BUNDLED_MONO = "JetBrains Mono"        # 自带代码字体


def load_fonts() -> dict:
    """把 fonts\\ 下的字体注册进 Qt。必须在 QApplication 建好之后调用。"""
    global _fonts_loaded, UI_FAMILY, MONO_FONT_FAMILY, ICON_FAMILY
    global BUNDLED_UI, BUNDLED_MONO
    result = {}
    if _fonts_loaded:
        return result

    try:
        from PySide6.QtGui import QFontDatabase
    except Exception:
        return result

    if not _FONT_DIR.is_dir():
        return result

    wanted = [
        ("NotoSansSC", "ui"),
        ("JetBrainsMono", "mono"),
        ("fasolid", "icon"),
    ]
    for path in sorted(_FONT_DIR.iterdir()):
        if path.suffix.lower() not in (".ttf", ".otf", ".ttc"):
            continue
        fid = QFontDatabase.addApplicationFont(str(path))
        if fid < 0:
            continue
        fams = QFontDatabase.applicationFontFamilies(fid)
        if not fams:
            continue
        fam = fams[0]
        stem = path.stem.replace("-", "").replace("_", "").lower()
        for key, kind in wanted:
            if key.lower() in stem:
                if kind == "ui":
                    UI_FAMILY = fam
                    BUNDLED_UI = fam
                elif kind == "mono":
                    MONO_FONT_FAMILY = fam
                    BUNDLED_MONO = fam
                elif kind == "icon":
                    ICON_FAMILY = fam
                result[path.name] = fam
                break

    _fonts_loaded = True
    return result


def ui_font(size: float = 9.0, bold: bool = False):
    from PySide6.QtGui import QFont
    f = QFont(UI_FAMILY)
    f.setPointSizeF(size)
    if bold:
        f.setBold(True)
    return f


def mono_font(size: float = 10.0):
    from PySide6.QtGui import QFont
    f = QFont(MONO_FONT_FAMILY)
    f.setPointSizeF(size)
    return f


def icon_font(size: float = 12.0):
    from PySide6.QtGui import QFont
    f = QFont(ICON_FAMILY)
    f.setPointSizeF(size)
    return f


# ══════════════ 应用样式 ══════════════
# Material Design 2 的控件外观交给 qt-material（成熟的 MD2 主题库），
# 颜色与品牌细节由本文件的 qss() 叠在上面。
# 这样按钮/输入框/下拉框/复选框/滚动条这一大堆细节不用自己一个个写，
# 后面加控件也不会因为漏写样式而长得不一样。
_MD2_THEME_DARK = "dark_blue.xml"
_MD2_THEME_LIGHT = "light_blue.xml"

# qt-material 的底稿缓存：同一亮/暗基底换来换去时不用重新跑一遍，
# 换肤从 2 次 setStyleSheet 降成 1 次。
_base_sheet: str | None = None
_base_dark: bool | None = None


def set_families(ui: str = "", mono: str = ""):
    """设置里选了本机字体就覆盖自带的；空字符串 = 保持 load_fonts() 的结果。"""
    global UI_FAMILY, MONO_FONT_FAMILY
    if ui:
        UI_FAMILY = ui
    if mono:
        MONO_FONT_FAMILY = mono


def apply(app, which=None):
    """把 MD2 基底 + 品牌配色一次性套到 QApplication 上。

    切换主题时重复调用即可：先让 qt-material 重设基底，再叠我们的补丁，
    不会出现「样式越叠越长」的问题。which 可以是外观 id，也可以是 True/False。
    """
    global _base_sheet, _base_dark
    if which is not None:
        use(which)

    dark = is_dark()
    if _base_sheet is None or _base_dark != dark:
        try:
            from qt_material import apply_stylesheet
            apply_stylesheet(
                app,
                theme=_MD2_THEME_DARK if dark else _MD2_THEME_LIGHT,
                invert_secondary=not dark,
            )
            _base_sheet = app.styleSheet()
            _base_dark = dark
        except Exception:
            # qt-material 不在或主题名变了都不致命：下面的 qss() 本身是完整的
            _base_sheet = ""
            _base_dark = dark

    app.setStyleSheet((_base_sheet or "") + qss())
