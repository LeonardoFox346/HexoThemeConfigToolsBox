"""许可证与第三方依赖清单。改协议只改这一个文件。"""
from __future__ import annotations

from pathlib import Path

APP_LICENSE = "GPL-3.0-or-later"
APP_COPYRIGHT = "Copyright (c) 2026 LeonardoFox346"

from .paths import APP_DIR

LICENSE_FILE = APP_DIR / "LICENSE"
BADGE_FILE = APP_DIR / "app" / "assets" / "gplv3.png"
GPL_ZH_URL = "https://gnu.net.cn/licenses/gpl-3.0.html"

SHORT_NOTICE = (
    "本程序以 GNU General Public License v3.0 或更高版本（GPL-3.0-or-later）发布。"
    "可以自由使用、修改、分发；分发修改后的版本时，必须同样以 GPL 开源，并提供源代码。"
    "完整条款见程序目录下的 LICENSE 文件。"
)


def license_text() -> str:
    try:
        return LICENSE_FILE.read_text(encoding="utf-8")
    except Exception:
        return SHORT_NOTICE

# (显示名, 项目主页, 许可证, 图标名, 主题色)
PROJECTS = [
    ("Qt / PySide6", "https://www.qt.io/", "LGPL-3.0", "layer-group", "#41CD52"),
    ("Python", "https://www.python.org/", "PSF-2.0", "python", "#3776AB"),
    ("qt-material", "https://github.com/UN-GCPDS/qt-material", "BSD-2-Clause", "cube", "#7B61FF"),
    ("Python-Markdown", "https://python-markdown.github.io/", "BSD-3-Clause", "markdown", "#2B6CB0"),
    ("Pygments", "https://pygments.org/", "BSD-2-Clause", "code", "#D97706"),
    ("Font Awesome 7 Free", "https://fontawesome.com/", "SIL OFL 1.1 / CC BY 4.0", "font-awesome", "#528DD7"),
    ("JetBrains Mono", "https://github.com/JetBrains/JetBrainsMono", "SIL OFL 1.1", "code", "#E11D48"),
    ("Noto Sans CJK", "https://github.com/notofonts/noto-cjk", "SIL OFL 1.1", "font-awesome", "#0EA5E9"),
    ("Hexo", "https://hexo.io/", "MIT", "hexagon", "#0E83CD"),
    ("hexo-theme-anzhiyu", "https://github.com/anzhiyu-c/hexo-theme-anzhiyu", "见项目主页", "hexagon", "#7C3AED"),
    ("hexo-theme-butterfly", "https://github.com/jerryc127/hexo-theme-butterfly", "见项目主页", "hexagon", "#EC4899"),
]


def third_party_text() -> str:
    lines = ["第三方组件与许可", ""]
    for name, url, license_, _icon, _color in PROJECTS:
        lines.append(f"· {name} — {license_}")
        lines.append(f"  {url}")
    lines.append("")
    lines.append("以上组件分别遵循各自许可证；本程序以 GPL-3.0-or-later 发布。")
    lines.append("字体与图标按各自许可随程序分发，不再单独授权。")
    return "\n".join(lines)


def full_text() -> str:
    return license_text().strip() + "\n\n" + "─" * 30 + "\n\n" + third_party_text()

def badge_pixmap(height: int = 34):
    """GPLv3 徽标（app/assets/gplv3.png），没有就返回空图。"""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    pm = QPixmap(str(BADGE_FILE))
    if pm.isNull():
        return pm
    return pm.scaledToHeight(height, Qt.SmoothTransformation)
