"""纳多狐狐的写作台 —— 入口。"""
from __future__ import annotations

import sys
from pathlib import Path

# 允许直接 `python main.py` 运行
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from app import theme

APP_NAME = "纳多狐狐的写作台"


def detect_dark() -> bool:
    """跟随系统：Windows 的「应用深色模式」开关。取不到就默认深色。"""
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


def main() -> int:
    QApplication.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings, True)
    # QtWebEngine 要求：必须在 QApplication 创建之前打开共享 OpenGL 上下文，
    # 否则第一次打开「样式预览」会直接崩掉。
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("NardoFox")
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / "app.ico")))

    # 先把 fonts\ 里的字体注册进来（FA7 图标 / JetBrains Mono / 思源黑体），
    # 再套样式，否则 QSS 里的 font-family 会落回系统默认
    from app import paths, settings

    loaded = theme.load_fonts()
    # 设置里选了本机字体就覆盖；空字符串 = 用自带的
    theme.set_families(settings.get("ui_font"), settings.get("mono_font"))
    app.setFont(theme.ui_font(9.0))
    if loaded:
        print("[字体] " + "，".join(f"{k}" for k in loaded))

    # 设置里换过博客目录 / 主题配置就按那个来
    paths.configure(settings.get("blog") or None, settings.get("config") or None)

    tid = theme.resolve(settings.get("theme") or "auto")
    theme.apply(app, tid)

    from app.ui.oobe import OobeDialog
    from app.ui.window import MainWindow

    def build_main():
        """按当前设置建主窗口，并做一次淡入（和引导的淡出接上）。"""
        theme.set_families(settings.get("ui_font"), settings.get("mono_font"))
        app.setFont(theme.ui_font(9.0))
        paths.configure(settings.get("blog") or None, settings.get("config") or None)
        theme.apply(app, theme.resolve(settings.get("theme") or "auto"))
        w = MainWindow()
        w.setWindowOpacity(0.0)
        w.showMaximized()
        from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation
        a = QPropertyAnimation(w, b"windowOpacity", w)
        a.setDuration(320)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.start(QAbstractAnimation.DeleteWhenStopped)
        return w

    win = None
    smoke = "--smoke" in sys.argv
    if OobeDialog.should_show() and not smoke:
        # 引导期间先别让「关掉最后一个窗口」把程序带走（中间会短暂没有主窗口）
        app.setQuitOnLastWindowClosed(False)
        dlg = OobeDialog()
        holder = {}

        def on_done():
            holder["w"] = build_main()

        dlg.completed.connect(on_done)
        dlg.exec()
        app.setQuitOnLastWindowClosed(True)
        if getattr(dlg, "aborted", False):
            return 0
        win = holder.get("w")
    if win is None:
        win = build_main()
    if smoke:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1800, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
