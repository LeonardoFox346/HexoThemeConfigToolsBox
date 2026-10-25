"""设置 / 关于两个小对话框。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from .. import paths, settings, theme

VERSION = "2.9"
REPO = "https://github.com/LeonardoFox346/HexoThemeConfigToolsBox"
ISSUES = REPO + "/issues"

FONT_KEYS = [("ui_font", "正文"), ("mono_font", "代码")]


def _btn(text: str, slot, width: int | None = None) -> QPushButton:
    b = QPushButton(text)
    if width:
        b.setFixedWidth(width)
    b.clicked.connect(slot)
    return b


class SettingsDialog(QDialog):
    """外观 / 博客目录 / 主题配置 / 字体。路径和字体改完要重启，外观立即生效。"""

    def __init__(self, parent=None, on_theme=None):
        super().__init__(parent)
        self.on_theme = on_theme
        self.on_saved = None
        self.setWindowTitle("设置")
        self.setMinimumWidth(680)
        # 内容放进滚动区后不再撑高窗口：给个够用的高度，小屏幕也能滚
        self.resize(680, 780)
        self._build()
        self._load()

    # ── 界面 ──
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        row = 0

        def head(text):
            nonlocal row
            lab = QLabel(text)
            lab.setObjectName("SubHead")
            lab.setContentsMargins(0, 14, 0, 2)
            c = theme.c()
            lab.setStyleSheet(
                f"font-size:13px; font-weight:600; color:{c['accent']};"
                " background:transparent; border-bottom:1px solid " + c['line'] + ";"
                " padding-bottom:3px;")
            grid.addWidget(lab, row, 0, 1, 3)
            row += 1

        def line(label, widget, extra=None):
            nonlocal row
            grid.addWidget(QLabel(label), row, 0)
            if extra is None:
                grid.addWidget(widget, row, 1, 1, 2)
            else:
                grid.addWidget(widget, row, 1)
                grid.addWidget(extra, row, 2)
            row += 1

        def rowbox(*widgets, spacing=6):
            box = QWidget()
            h = QHBoxLayout(box)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(spacing)
            for w in widgets:
                h.addWidget(w)
            h.addStretch(1)
            return box

        # ── 外观 ──
        head("外观")
        self.cb_theme = QComboBox()
        self.cb_theme.addItem("跟随系统", "auto")
        for tid in theme.THEME_ORDER:
            self.cb_theme.addItem(theme.theme_name(tid), tid)
        self.cb_theme.currentIndexChanged.connect(self._theme_changed)
        line("主题", self.cb_theme)

        fams = []
        try:
            fams = sorted({f for f in QFontDatabase.families() if f})
        except Exception:
            pass
        self.cb_fonts: dict[str, QComboBox] = {}
        for key, label in FONT_KEYS:
            cb = QComboBox()
            bundled = theme.BUNDLED_UI if key == "ui_font" else theme.BUNDLED_MONO
            cb.addItem(f"默认（{bundled}）", "")
            for f in fams:
                cb.addItem(f, f)
            cb.setEditable(False)
            self.cb_fonts[key] = cb
            box = QWidget()
            h = QHBoxLayout(box)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            h.addWidget(cb, 1)
            h.addWidget(_btn("回到默认", lambda _=False, k=key: self.cb_fonts[k].setCurrentIndex(0), 84))
            line(label, box)

        icon = QLabel(theme.ICON_FAMILY)
        icon.setObjectName("Dim")
        line("图标", icon)

        # ── 博客 ──
        head("博客")
        self.ed_blog = QLineEdit()
        self.ed_blog.setPlaceholderText(str(paths.DEFAULT_BLOG))
        line("博客目录", self.ed_blog, _btn("浏览…", self._pick_blog, 76))

        self.ed_cfg = QLineEdit()
        self.ed_cfg.setPlaceholderText("默认 <博客目录>/_config.anzhiyu.yml")
        cfg_btns = rowbox(_btn("浏览…", self._pick_cfg, 76), _btn("默认", self._reset_cfg, 56))
        line("主题配置", self.ed_cfg, cfg_btns)

        self._data_dirty = False
        data_hint = QLabel("五个 _data 文件的路径（默认按上面的博客目录推导，保存前请确认）")
        data_hint.setObjectName("Dim")
        line("数据文件", data_hint, _btn("修改…", self._open_data_files, 84))

        self.chk_hidden: dict[str, QCheckBox] = {}
        hidden = set(settings.get_hidden_pages())
        for name in ("装备", "相册", "技能"):
            cb = QCheckBox(name)
            cb.setChecked(name in hidden)
            self.chk_hidden[name] = cb
        hide_box = rowbox(*self.chk_hidden.values(), spacing=14)
        line("侧边栏隐藏", hide_box)

        # ── 编辑器 ──
        head("编辑器")
        self.chk_editor: dict[str, QCheckBox] = {}
        for key, label in (("ed_sync", "同步滚动"), ("ed_preview", "同步预览"),
                           ("ed_style", "样式预览"), ("ed_immersive", "沉浸")):
            cb = QCheckBox(label)
            auto_on = key in ("ed_sync", "ed_preview")
            cb.setChecked(settings.get(key) != "0" if auto_on else settings.get(key) == "1")
            self.chk_editor[key] = cb
        ed_box = rowbox(*self.chk_editor.values(), spacing=14)
        line("默认开关", ed_box)

        # ── 服务器与发布 ──
        head("服务器与发布")
        self.ed_server = QLineEdit()
        self.ed_server.setPlaceholderText("IP 或 ~/.ssh/config 里的别名；留空用 blog-server")
        line("服务器地址", self.ed_server)

        self.ed_ssh_key = QLineEdit()
        self.ed_ssh_key.setPlaceholderText("私钥文件路径；留空 = ~/.ssh 里的默认密钥")
        key_box = rowbox(_btn("浏览…", lambda: self._pick_key(self.ed_ssh_key), 76),
                         _btn("默认", lambda: self.ed_ssh_key.setText(""), 56))
        line("SSH 密钥", self.ed_ssh_key, key_box)

        self.ed_pass = QLineEdit()
        self.ed_pass.setEchoMode(QLineEdit.Password)
        self.ed_pass.setPlaceholderText("只做记录；免密请把密钥 ssh-add 到 agent")
        self.ed_pass.setToolTip("ssh.exe 在 BatchMode 下不会读这个密码；带密码短语的密钥要先 ssh-add 进 agent。")
        line("密钥密码", self.ed_pass)

        self.ed_repo = QLineEdit()
        self.ed_repo.setPlaceholderText("owner/repo 或 https://github.com/owner/repo")
        line("GitHub 仓库", self.ed_repo)

        self.ed_gh_key = QLineEdit()
        self.ed_gh_key.setPlaceholderText("GitHub 用的私钥路径")
        gh_box = rowbox(_btn("浏览…", lambda: self._pick_key(self.ed_gh_key), 76),
                        _btn("默认", lambda: self.ed_gh_key.setText(""), 56))
        line("GitHub 密钥", self.ed_gh_key, gh_box)

        self.cb_push = QComboBox()
        self.cb_push.addItem("服务器 + GitHub 备份", "both")
        self.cb_push.addItem("只推服务器（跳过源码备份）", "server")
        self.cb_push.addItem("只推 GitHub 仓库（适用于 GitHub Pages）", "github")
        line("推送方式", self.cb_push)

        self.chk_proxy = QCheckBox("允许代理（连 GitHub 用；服务器采集仍会被拦）")
        self.chk_proxy.setToolTip("有些人必须挂代理才能连上 GitHub。勾上后发布页默认跳过代理检查。")
        line("代理", self.chk_proxy)

        # ── 其它 ──
        head("其它")
        self.chk_persist = QCheckBox("退出后保留设置")
        self.chk_persist.setChecked(settings.persist())
        self.chk_persist.setToolTip("勾上：改完立即写进 settings.json；取消：只在本次运行里生效。")
        line("持久化", self.chk_persist)

        path_tip = QLabel(f"配置文件：{settings.CONFIG_PATH}")
        path_tip.setObjectName("Dim")
        path_tip.setWordWrap(True)
        grid.addWidget(path_tip, row, 0, 1, 3)
        row += 1

        def _open_issues():
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(ISSUES))

        tools_box = rowbox(_btn("导出配置…", self._export, 120),
                           _btn("导入配置…", self._import, 120),
                           _btn("反馈问题", lambda: _open_issues(), 110),
                           _btn("许可协议", self._open_eula, 100),
                           _btn("开源许可", self._open_license, 100),
                           _btn("关于", self._open_about, 80),
                           _btn("重新运行引导", self._rerun_oobe, 120), spacing=8)
        grid.addWidget(tools_box, row, 0, 1, 3)
        row += 1

        inner = QWidget()
        ilay = QVBoxLayout(inner)
        ilay.setContentsMargins(0, 0, 0, 0)
        ilay.setSpacing(8)
        ilay.addLayout(grid)

        tip = QLabel("外观改完立即生效；博客目录 / 主题配置 / 字体要重启程序才生效。")
        tip.setWordWrap(True)
        tip.setObjectName("Dim")
        ilay.addWidget(tip)

        from PySide6.QtWidgets import QFrame, QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("保存")
        bb.button(QDialogButtonBox.Cancel).setText("取消")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        from . import badges as _badges
        foot = QHBoxLayout()
        foot.addWidget(_badges.gpl_badge(26))
        foot.addStretch(1)
        foot.addWidget(bb)
        root.addLayout(foot)

    def _rerun_oobe(self):
        # 不在设置窗里嵌套打开：容易和主题切换 / 特效打架。
        # 改成「标记未完成 + 重启」，启动时自然会再弹引导。
        if QMessageBox.question(
                self, "重新运行引导",
                "会重启程序，然后显示首次启动引导。\n\n"
                "没保存的改动会丢，建议先点「保存」。继续？") != QMessageBox.Yes:
            return
        settings.put("oobe_done", "")
        settings.put("oobe_skipped", "")
        self._restart()

    def _gpl_badge(self):
        from . import badges
        return badges.gpl_badge(24)

    def _open_eula(self):
        from .dlg_eula import EulaDialog
        EulaDialog(self).exec()

    def _open_license(self):
        from .about import LicenseDialog
        LicenseDialog(self).exec()

    def _open_about(self):
        from .about import AboutDialog
        AboutDialog(self).exec()

    # ── 读 / 写 ──
    def _pick_key(self, target: QLineEdit):
        start = str(Path.home() / ".ssh")
        f, _ = QFileDialog.getOpenFileName(self, "选私钥", start, "密钥文件 (*)")
        if f:
            target.setText(f)

    def _load(self):
        tid = settings.get("theme") or "auto"
        i = self.cb_theme.findData(tid)
        self.cb_theme.blockSignals(True)
        self.cb_theme.setCurrentIndex(max(0, i))
        self.cb_theme.blockSignals(False)

        self.ed_server.setText(settings.get("server_host") or "blog-server")
        self.ed_server.setToolTip(
            "填服务器 IP，或 ~/.ssh/config 里的别名；留空 / 显示 blog-server 表示用内置默认。")
        self.ed_ssh_key.setText(settings.get("ssh_key"))
        self.ed_pass.setText(settings.get("ssh_pass"))
        self.ed_repo.setText(settings.get("github_repo"))
        self.ed_gh_key.setText(settings.get("github_key"))
        i = self.cb_push.findData(settings.get("push_mode") or "both")
        self.cb_push.setCurrentIndex(max(0, i))
        self.chk_proxy.setChecked(settings.get("allow_proxy") == "1")
        self.chk_persist.setChecked(settings.persist())
        self.ed_blog.setPlaceholderText(f"默认：{paths.DEFAULT_BLOG}")
        self.ed_blog.setText(settings.get("blog"))
        self.ed_cfg.setPlaceholderText("留空 = <博客目录>/_config.anzhiyu.yml（找不到会退到 _config.*.yml）")
        self.ed_cfg.setText(settings.get("config"))
        for key, _ in FONT_KEYS:
            val = settings.get(key)
            cb = self.cb_fonts[key]
            j = cb.findData(val)
            cb.setCurrentIndex(max(0, j) if val else 0)

    def _theme_changed(self, *_):
        tid = self.cb_theme.currentData()
        if not tid:
            return
        settings.put("theme", tid)
        theme.use(theme.resolve(tid))
        if self.on_theme:
            self.on_theme()

    def _pick_blog(self):
        d = QFileDialog.getExistingDirectory(self, "选博客目录", self.ed_blog.text() or str(paths.DEFAULT_BLOG))
        if d:
            self.ed_blog.setText(d)

    def _open_data_files(self):
        blog = self.ed_blog.text().strip() or str(paths.DEFAULT_BLOG)
        dlg = DataFilesDialog(self, blog_dir=blog)
        if dlg.exec() == QDialog.Accepted:
            self._data_dirty = True

    def _pick_cfg(self):
        f, _ = QFileDialog.getOpenFileName(self, "选主题配置文件",
                                           self.ed_cfg.text() or str(paths.BLOG),
                                           "YAML (*.yml *.yaml)")
        if f:
            self.ed_cfg.setText(f)

    def _reset_cfg(self):
        self.ed_cfg.setText(str(Path(self.ed_blog.text() or paths.DEFAULT_BLOG) / "_config.anzhiyu.yml"))

    def _save(self):
        settings.set_hidden_pages(
            [n for n, cb in self.chk_hidden.items() if cb.isChecked()])
        old = {
            "blog": settings.get("blog"),
            "config": settings.get("config"),
            "ui_font": settings.get("ui_font"),
            "mono_font": settings.get("mono_font"),
        }
        blog = self.ed_blog.text().strip()
        cfg = self.ed_cfg.text().strip()
        if blog and Path(blog) == paths.DEFAULT_BLOG:
            blog = ""
        if cfg and Path(cfg) == Path(blog or paths.DEFAULT_BLOG) / "_config.anzhiyu.yml":
            cfg = ""
        settings.put("blog", blog)
        settings.put("config", cfg)
        settings.put("server_host", self.ed_server.text().strip())
        settings.put("ssh_key", self.ed_ssh_key.text().strip())
        settings.put("ssh_pass", self.ed_pass.text())
        settings.put("github_repo", self.ed_repo.text().strip())
        settings.put("github_key", self.ed_gh_key.text().strip())
        settings.put("push_mode", self.cb_push.currentData() or "both")
        settings.set_persist(self.chk_persist.isChecked())
        for key, cb in self.chk_editor.items():
            settings.put(key, "1" if cb.isChecked() else "0")
        settings.put("allow_proxy", "1" if self.chk_proxy.isChecked() else "0")
        for key, _ in FONT_KEYS:
            settings.put(key, self.cb_fonts[key].currentData() or "")

        if callable(self.on_saved):
            self.on_saved()
        changed = self._data_dirty or any(old[k] != settings.get(k) for k in old)
        if changed:
            box = QMessageBox(self)
            box.setWindowTitle("要重启才生效")
            box.setText("博客目录 / 主题配置 / 字体改完要重启程序才生效。\n现在重启吗？")
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.button(QMessageBox.Yes).setText("现在重启")
            box.button(QMessageBox.No).setText("稍后")
            if box.exec() == QMessageBox.Yes:
                self._restart()
                return
        self.accept()

    def _import(self):
        f, _ = QFileDialog.getOpenFileName(self, "选配置文件",
                                           str(Path.home()), "JSON (*.json)")
        if not f:
            return
        try:
            data = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.critical(self, "读不了这个文件", str(e))
            return
        if QMessageBox.question(
                self, "导入配置",
                "会用文件里的设置覆盖当前设置（博客目录 / 字体 / 服务器 / GitHub 等）。\n继续？"
        ) != QMessageBox.Yes:
            return
        from ..export_config import apply_import
        n = apply_import(data)
        self._load()
        if self.on_theme:
            self.on_theme()
        if callable(self.on_saved):
            self.on_saved()
        QMessageBox.information(
            self, "已导入",
            f"导入 {n} 项。\n\n博客目录 / 字体要重启程序才生效。")

    def _export(self):
        from PySide6.QtCore import QStandardPaths
        desk = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
        if not desk:
            desk = str(Path.home() / "Desktop")
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        from ..export_config import build_export
        js, md = build_export()
        f1 = Path(desk) / f"写作台配置-{ts}.json"
        f2 = Path(desk) / f"写作台配置说明-{ts}.md"
        try:
            f1.write_text(js, encoding="utf-8")
            f2.write_text(md, encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
            return
        QMessageBox.information(self, "已导出", f"{f1}\n{f2}")

    @staticmethod
    def _restart():
        from PySide6.QtWidgets import QApplication
        QProcess.startDetached(sys.executable, [sys.argv[0], *sys.argv[1:]])
        QApplication.quit()


class DataFilesDialog(QDialog):
    """_data 文件位置：可以指定一个文件夹（五个文件都在里面），也可以单个指定 yml。"""

    ROWS = [
        ("data_about", "关于页数据", "about.yml"),
        ("data_equipment", "装备", "equipment.yml"),
        ("data_link", "友链增删", "link.yml"),
        ("data_album", "相册", "album.yml"),
        ("data_skills", "技能", "creativity.yml"),
    ]

    def __init__(self, parent=None, blog_dir=None):
        super().__init__(parent)
        self.setWindowTitle("数据文件位置")
        self.resize(740, 430)
        # 默认位置跟着「博客目录」走：设置里填哪个目录，这里就按哪个目录预填
        root = Path(blog_dir).expanduser() if blog_dir else paths.DEFAULT_BLOG
        self.base_default = root / "source" / "_data"

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        warn = QLabel("⚠ 下面的默认位置是按「博客目录」推出来的，保存前请逐个确认对不对；"
                      "不对就用「文件夹…」或「文件…」自己选。")
        warn.setWordWrap(True)
        warn.setStyleSheet("color:#C9A227; background:transparent;")
        root.addWidget(warn)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        self.ed_dir = QLineEdit(settings.get("data_dir"))
        self.ed_dir.setPlaceholderText("默认：" + str(self.base_default))
        self.ed_dir.textChanged.connect(self._refresh_placeholders)
        grid.addWidget(QLabel("数据文件夹"), 0, 0)
        grid.addWidget(self.ed_dir, 0, 1)
        dir_btns = QWidget()
        dh = QHBoxLayout(dir_btns)
        dh.setContentsMargins(0, 0, 0, 0)
        dh.setSpacing(6)
        dh.addWidget(_btn("文件夹…", self._pick_dir, 76))
        dh.addWidget(_btn("默认", lambda: self.ed_dir.setText(""), 56))
        grid.addWidget(dir_btns, 0, 2)

        self.edits: dict[str, QLineEdit] = {}
        self.labels: dict[str, QLabel] = {}
        for row, (key, label, filename) in enumerate(self.ROWS, start=1):
            ed = QLineEdit(settings.get(key))
            ed.textChanged.connect(self._refresh_placeholders)
            self.edits[key] = ed
            lab = QLabel(label)
            self.labels[key] = lab
            grid.addWidget(lab, row, 0)
            grid.addWidget(ed, row, 1)
            btns = QWidget()
            h = QHBoxLayout(btns)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            h.addWidget(_btn("文件…", lambda _=False, e=ed: self._pick_file(e), 66))
            h.addWidget(_btn("默认", lambda _=False, e=ed: e.setText(""), 56))
            grid.addWidget(btns, row, 2)
        root.addLayout(grid)

        tip = QLabel("两层都留空就用 <博客目录>/source/_data。文件名可写相对名或绝对路径；改完要重启程序才生效。")
        tip.setObjectName("Dim")
        tip.setWordWrap(True)
        root.addWidget(tip)
        root.addStretch(1)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("保存")
        bb.button(QDialogButtonBox.Cancel).setText("取消")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)
        self._refresh_placeholders()

    def _base(self) -> Path:
        v = self.ed_dir.text().strip()
        if not v:
            return self.base_default
        p = Path(v)
        return p if p.is_absolute() else self.base_default / p

    def _refresh_placeholders(self):
        base = self._base()
        for key, label, filename in self.ROWS:
            v = self.edits[key].text().strip()
            target = Path(v) if v else base / filename
            if not target.is_absolute():
                target = base / target
            ed = self.edits[key]
            exists = target.exists()
            ed.setPlaceholderText("默认：" + str(target) + ("" if exists else "　（没找到这个文件）"))
            note = "文件存在" if exists else "文件不存在：保存前请确认"
            ed.setToolTip(str(target) + chr(10) + note)
            lab = self.labels[key]
            lab.setText(label if exists else label + "（缺）")
            lab.setToolTip("" if exists else f"没找到：{target}")

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选数据文件夹", str(self._base()))
        if d:
            self.ed_dir.setText(d)

    def _pick_file(self, ed: QLineEdit):
        start = self._base()
        v = ed.text().strip()
        if v:
            p = Path(v)
            start = p.parent if p.is_absolute() else self._base()
        f, _ = QFileDialog.getOpenFileName(self, "选 yml 文件", str(start), "YAML (*.yml *.yaml)")
        if f:
            ed.setText(f)

    def _save(self):
        settings.put("data_dir", self.ed_dir.text().strip())
        for key, ed in self.edits.items():
            settings.put(key, ed.text().strip())
        self.accept()
