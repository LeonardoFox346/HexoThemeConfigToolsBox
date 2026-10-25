"""首次启动引导（OOBE）：环境自检 → 博客目录 → 主题配置 → 服务器 → 外观 → 完成。"""
from __future__ import annotations

import random
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QPropertyAnimation, Signal,                            QRect, Qt, QTimer, QVariantAnimation)
from PySide6.QtGui import QColor, QFontDatabase, QPainter
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from .. import eula, licenses, paths, remote, settings, theme
from . import badges, icons

APP_TITLE = "纳多狐狐的写作台"


def _run(cmd, timeout=6.0):
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
        out = (p.stdout or b"").decode("utf-8", "replace").strip()
        err = (p.stderr or b"").decode("utf-8", "replace").strip()
        return p.returncode == 0, (out or err).splitlines()[0] if (out or err) else ""
    except Exception as e:
        return False, str(e)


def pop_in(label, size, name="circle-check", ms=460):
    """图标从小到大弹出来（OutBack 有一点回弹）。"""
    anim = QVariantAnimation(label)
    anim.setStartValue(0.35)
    anim.setEndValue(1.0)
    anim.setDuration(ms)
    anim.setEasingCurve(QEasingCurve.OutBack)

    def upd(v):
        px = max(10, int(size * float(v)))
        label.setPixmap(icons.fa_pixmap(name, px, theme.c()["good"]))
        label.setFixedSize(px, px)

    anim.valueChanged.connect(upd)
    anim.start(QAbstractAnimation.DeleteWhenStopped)
    return anim


def fade_in(widget, ms=260):
    from PySide6.QtWidgets import QGraphicsOpacityEffect
    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    a = QPropertyAnimation(eff, b"opacity", widget)
    a.setDuration(ms)
    a.setStartValue(0.0)
    a.setEndValue(1.0)
    a.setEasingCurve(QEasingCurve.OutCubic)

    def done():
        widget.setGraphicsEffect(None)

    a.finished.connect(done)
    a.start(QAbstractAnimation.DeleteWhenStopped)
    return a


class Confetti(QWidget):
    """完成页彩带：canvas-confetti 那套物理（重力 / 衰减 / 角度扇形）。"""

    COLORS = ["#f2b705", "#ef476f", "#06d6a0", "#118ab2", "#ffd166", "#8ecae6", "#f78c6b"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.particles = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.hide()

    def burst(self, ox, oy, angle, count=70, spread=60, velocity=560, scalar=1.0):
        import math
        base = math.radians(angle)
        w, h = max(1, self.width()), max(1, self.height())
        for _ in range(count):
            a = base + math.radians(random.uniform(-spread / 2, spread / 2))
            v = velocity * random.uniform(0.55, 1.0)
            self.particles.append({
                "x": ox * w, "y": oy * h,
                "vx": math.cos(a) * v, "vy": -math.sin(a) * v,
                "w": random.uniform(4, 8) * scalar,
                "h": random.uniform(3, 6) * scalar,
                "rot": random.uniform(0, 360), "vr": random.uniform(-320, 320),
                "c": QColor(random.choice(self.COLORS)),
                "life": 1.0, "circle": random.random() < 0.35,
            })
        self.show()
        self.raise_()
        if not self.timer.isActive():
            self.timer.start(16)

    def celebrate(self):
        """两侧斜向上打，再补两发，像 GitHub 上常见的那种。"""
        self.burst(0.02, 0.78, 62, 90, 58, 620)
        self.burst(0.98, 0.78, 118, 90, 58, 620)
        QTimer.singleShot(320, lambda: self.burst(0.12, 0.92, 72, 70, 52, 560))
        QTimer.singleShot(560, lambda: self.burst(0.88, 0.92, 108, 70, 52, 560))
        QTimer.singleShot(900, lambda: self.burst(0.5, 0.98, 90, 50, 70, 520))

    def stop(self):
        self.timer.stop()
        self.particles = []
        self.hide()

    def _tick(self):
        dt = 0.016
        alive = []
        for p in self.particles:
            p["vy"] += 720 * dt
            p["vx"] *= 0.996
            p["vy"] *= 0.996
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["rot"] += p["vr"] * dt
            p["life"] -= dt * 0.28
            if p["life"] > 0 and p["y"] < self.height() + 40:
                alive.append(p)
        self.particles = alive
        if not alive:
            self.stop()
            return
        self.update()

    def paintEvent(self, _e):
        q = QPainter(self)
        q.setRenderHint(QPainter.Antialiasing)
        for p in self.particles:
            q.save()
            q.setOpacity(max(0.0, min(1.0, p["life"])))
            q.translate(p["x"], p["y"])
            q.rotate(p["rot"])
            q.setPen(Qt.NoPen)
            q.setBrush(p["c"])
            if p["circle"]:
                r = p["w"] / 2
                q.drawEllipse(QRect(int(-r), int(-r), int(p["w"]), int(p["w"])))
            else:
                q.drawRoundedRect(
                    QRect(int(-p["w"] / 2), int(-p["h"] / 2), int(p["w"]), int(p["h"])), 1.0, 1.0)
            q.restore()


class Stage(QWidget):
    """背景极光：几团缓慢漂移的柔光，靠主题色，不影响点击。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.t = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)

    def _tick(self):
        if not self.isVisible():
            return
        self.t += 0.010
        self.update()

    def paintEvent(self, _e):
        import math
        from PySide6.QtGui import QRadialGradient
        p = theme.c()
        q = QPainter(self)
        q.setRenderHint(QPainter.Antialiasing)
        q.setPen(Qt.NoPen)
        w, h = max(1, self.width()), max(1, self.height())
        blobs = [
            (0.18, 0.22, p["accent"], 0.20, 1.0),
            (0.82, 0.18, p["accent_soft"], 0.24, 1.3),
            (0.62, 0.92, p["accent"], 0.16, 0.8),
        ]
        for i, (bx, by, col, alpha, sp) in enumerate(blobs):
            cx = w * (bx + 0.05 * math.sin(self.t * sp + i * 1.7))
            cy = h * (by + 0.04 * math.cos(self.t * sp * 0.8 + i))
            r = 0.55 * max(w, h)
            g = QRadialGradient(cx, cy, r)
            c1 = QColor(col)
            c1.setAlphaF(alpha)
            c2 = QColor(col)
            c2.setAlphaF(0.0)
            g.setColorAt(0.0, c1)
            g.setColorAt(1.0, c2)
            q.setBrush(g)
            q.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

class Page(QWidget):
    """一屏。validate 返回 (能不能继续, 提示)。"""

    title = ""

    def __init__(self, dlg):
        super().__init__(dlg)
        self.dlg = dlg
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(24, 8, 24, 8)
        self.v.setSpacing(10)

    def on_enter(self):
        pass

    def validate(self):
        return True, ""

    def can_advance(self) -> bool:
        return True

    def head(self, title: str, sub: str = ""):
        t = QLabel(title)
        t.setObjectName("OobeTitle")
        self.v.addWidget(t)
        if sub:
            s = QLabel(sub)
            s.setObjectName("OobeSub")
            s.setWordWrap(True)
            self.v.addWidget(s)


VER_OK = "#2e9e5b"
VER_BAD = "#c0392b"


class WelcomePage(Page):
    title = "欢迎与环境"

    CHECKS = [
        ("python", "Python", "装 Python 3.10+，装好点「重新检测」"),
        ("pyside", "PySide6", "pip install PySide6"),
        ("node", "Node.js", "装 Node.js LTS（含 npm），装好点「重新检测」"),
        ("git", "Git", "装 Git for Windows"),
        ("hexo", "hexo-cli", "在博客目录执行 npm install"),
        ("modules", "node_modules", "在博客目录执行 npm install"),
        ("fonts", "字体", "把 fonts/ 放回程序目录"),
    ]

    def __init__(self, dlg):
        super().__init__(dlg)
        head = QHBoxLayout()
        head.setSpacing(16)
        logo = QLabel()
        logo.setPixmap(icons.fox_logo(84))
        logo.setFixedSize(84, 84)
        self.logo = logo
        head.addWidget(logo, 0, Qt.AlignTop)
        tv = QVBoxLayout()
        tv.setSpacing(4)
        t = QLabel("欢迎使用" + APP_TITLE)
        t.setObjectName("OobeHero")
        tv.addWidget(t)
        s = QLabel("给 Hexo + Anzhiyu / Butterfly 等博客用的桌面工具：写文章、看状态、改配置、一键发布。")
        s.setObjectName("OobeSub")
        s.setWordWrap(True)
        tv.addWidget(s)
        tv.addStretch(1)
        head.addLayout(tv, 1)
        self.v.addLayout(head)

        self.rows = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)
        for i, (key, name, fix) in enumerate(self.CHECKS):
            lab = QLabel(name)
            st = QLabel("等待检查")
            st.setObjectName("OobeStatus")
            fixlab = QLabel("")
            fixlab.setObjectName("OobeFix")
            fixlab.setWordWrap(True)
            grid.addWidget(lab, i, 0)
            grid.addWidget(st, i, 1)
            grid.addWidget(fixlab, i, 2)
            grid.setColumnStretch(2, 1)
            self.rows[key] = (st, fixlab, fix)
        self.v.addLayout(grid)
        self.v.addStretch(1)

        foot = QHBoxLayout()
        self.btn_again = QPushButton("重新检测")
        self.btn_again.clicked.connect(self.run_checks)
        foot.addWidget(self.btn_again)
        tip = QLabel("环境不全也能继续，只是后面的「构建 / 发布」用不了。")
        tip.setObjectName("OobeFix")
        foot.addWidget(tip)
        foot.addStretch(1)
        self.v.addLayout(foot)

    def on_enter(self):
        fade_in(self.logo, 320)

    def _set(self, key, ok, text):
        st, fix, fx = self.rows[key]
        st.setText(("✓ " if ok else "✗ ") + text)
        fade_in(st, 140)
        fade_in(fix, 140)
        st.setStyleSheet("color:" + (VER_OK if ok else VER_BAD) + "; background:transparent;")
        fix.setText("" if ok else "→ " + fx)

    def run_checks(self):
        for key in self.rows:
            st, fix, _ = self.rows[key]
            st.setText("检查中…")
            st.setStyleSheet("color:gray; background:transparent;")
            fix.setText("")
        self.btn_again.setEnabled(False)
        steps = list(self._steps())
        delay = 60

        def run(i=0):
            if i >= len(steps):
                self.btn_again.setEnabled(True)
                return
            steps[i]()
            QTimer.singleShot(delay, lambda: run(i + 1))

        QTimer.singleShot(60, run)

    def _steps(self):
        yield lambda: self._set(
            "python", sys.version_info >= (3, 10),
            sys.version.split()[0] if sys.version_info >= (3, 10) else "版本过低")
        yield lambda: self._set_pyside()
        yield lambda: self._set_tool("node", "node", ["node", "--version"])
        yield lambda: self._set_tool("git", "git", ["git", "--version"])
        yield lambda: self._set_hexo()
        yield lambda: self._set_modules()
        yield lambda: self._set_fonts()

    def _set_pyside(self):
        try:
            import PySide6
            self._set("pyside", True, PySide6.__version__)
        except Exception as e:
            self._set("pyside", False, str(e))

    def _set_tool(self, key, exe, cmd):
        if not shutil.which(exe):
            self._set(key, False, "未找到")
            return
        ok, out = _run(cmd)
        txt = out.lstrip("v") if out.startswith("v") else out
        self._set(key, ok, txt if ok else "找到但跑不起来")

    def _blog(self) -> Path:
        return self.dlg.blog_page.blog_dir()

    def _set_hexo(self):
        cli = self._blog() / "node_modules" / "hexo-cli" / "bin" / "hexo"
        if cli.exists():
            self._set("hexo", True, "已安装")
        else:
            self._set("hexo", False, "博客目录里没有，选完博客目录再检测")

    def _set_modules(self):
        nm = self._blog() / "node_modules"
        if nm.exists():
            self._set("modules", True, "存在")
        else:
            self._set("modules", False, "博客目录里没有，先 npm install")

    def _set_fonts(self):
        d = paths.APP_DIR / "fonts"
        n = len(list(d.glob("*.ttf"))) + len(list(d.glob("*.otf"))) if d.exists() else 0
        self._set("fonts", n > 0, ("%d 个字体文件" % n) if n else "fonts/ 里没有字体")


class EulaPage(Page):
    title = "许可协议"

    def __init__(self, dlg):
        super().__init__(dlg)
        self.head("软件使用许可协议", "安装或使用前请阅读。同意后继续；不同意请关闭程序。")
        from PySide6.QtWidgets import QTextBrowser
        br = QTextBrowser()
        br.setObjectName("EulaBox")
        br.setOpenExternalLinks(True)
        br.setPlainText(eula.EULA_TEXT)
        self.v.addWidget(br, 1)
        self.ack = QCheckBox("我已阅读并同意《软件使用许可协议》")
        self.ack.toggled.connect(self._ack_changed)
        self.v.addWidget(self.ack)

    def _ack_changed(self, on: bool):
        if hasattr(self.dlg, "btn_next"):
            self.dlg.btn_next.setEnabled(on)

    def can_advance(self) -> bool:
        return bool(getattr(self, "ack", None) and self.ack.isChecked())


class BlogPage(Page):
    title = "博客目录"

    def __init__(self, dlg):
        super().__init__(dlg)
        self.head("博客目录", "选 Hexo 博客的根目录（有 _config.yml、source/_posts、package.json 的那一层）。也可以跳过。")
        row = QHBoxLayout()
        self.ed = QLineEdit(settings.get("blog"))
        self.ed.setPlaceholderText("例如 D:/WEB/blog")
        self.ed.textChanged.connect(self._later)
        b = QPushButton("浏览…")
        b.clicked.connect(self._pick)
        row.addWidget(self.ed, 1)
        row.addWidget(b)
        self.v.addLayout(row)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        self.v.addWidget(self.msg)
        self.probe = QLabel("")
        self.probe.setWordWrap(True)
        self.probe.setObjectName("OobeFix")
        self.v.addWidget(self.probe)
        self.v.addStretch(1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.check)
        self.check()

    def _later(self):
        self._timer.start(250)

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "选博客目录", self.ed.text() or str(paths.DEFAULT_BLOG))
        if d:
            self.ed.setText(d)
            self.check()

    def blog_dir(self) -> Path:
        v = self.ed.text().strip()
        return Path(v) if v else paths.DEFAULT_BLOG

    def check(self):
        self._timer.stop()
        v = self.ed.text().strip()
        if not v:
            self.msg.setText("可以跳过：程序会先用默认目录 " + str(paths.DEFAULT_BLOG) + "。")
            self.msg.setStyleSheet("color:gray; background:transparent;")
            self.probe.setText("")
            return
        root = Path(v)
        if not root.exists():
            self.msg.setText("✗ 这个目录不存在")
            self.msg.setStyleSheet("color:" + VER_BAD + "; background:transparent;")
            return
        need = [("_config.yml", root / "_config.yml"),
                ("source/_posts", root / "source" / "_posts"),
                ("package.json", root / "package.json")]
        missing = [name for name, p in need if not p.exists()]
        if missing:
            self.msg.setText("✗ 还缺：" + "、".join(missing))
            self.msg.setStyleSheet("color:" + VER_BAD + "; background:transparent;")
            self.probe.setText("")
            return
        posts = list((root / "source" / "_posts").rglob("*.md"))
        cands = sorted(p.name for p in root.glob("_config.*.yml"))
        self.msg.setText("✓ 目录可用")
        self.msg.setStyleSheet("color:" + VER_OK + "; background:transparent;")
        self.probe.setText("文章 %d 篇　·　主题配置候选：%s"
                           % (len(posts), "、".join(cands) if cands else "（没有 _config.*.yml）"))
        self.dlg.theme_page.rescan()

    def validate(self):
        v = self.ed.text().strip()
        if not v:
            return True, ""
        root = Path(v)
        if not root.exists():
            return False, "这个目录不存在"
        if not (root / "_config.yml").exists():
            return False, "这个目录里没有 _config.yml，不像是 Hexo 博客"
        return True, ""


class ThemePage(Page):
    title = "主题配置"

    def __init__(self, dlg):
        super().__init__(dlg)
        self.head("主题配置", "程序自动扫 <博客目录>/_config.*.yml。选一个就行，也可以留空用默认路径。")
        self.list = QListWidget()
        self.list.setMinimumHeight(150)
        self.v.addWidget(self.list, 1)
        row = QHBoxLayout()
        b = QPushButton("重新扫描")
        b.clicked.connect(self.rescan)
        row.addWidget(b)
        self.msg = QLabel("")
        self.msg.setObjectName("OobeFix")
        row.addWidget(self.msg, 1)
        self.v.addLayout(row)
        self.probe = QLabel("")
        self.probe.setWordWrap(True)
        self.probe.setObjectName("OobeFix")
        self.v.addWidget(self.probe)

    def rescan(self):
        base = self.dlg.blog_page.blog_dir()
        cur = self.chosen()
        self.list.clear()
        item = QListWidgetItem("（留空：用 <博客目录>/_config.anzhiyu.yml）")
        item.setData(Qt.UserRole, "")
        self.list.addItem(item)
        cands = sorted(base.glob("_config.*.yml"))
        for p in cands:
            it = QListWidgetItem(p.name + "　·　" + str(p))
            it.setData(Qt.UserRole, str(p))
            self.list.addItem(it)
        want = settings.get("config") or cur
        idx = 0
        for i in range(self.list.count()):
            if want and self.list.item(i).data(Qt.UserRole) == want:
                idx = i
        if idx == 0:
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole).endswith("_config.anzhiyu.yml"):
                    idx = i
                    break
        self.list.setCurrentRow(idx)
        self.msg.setText("扫到 %d 个 _config.*.yml" % len(cands))

    def on_enter(self):
        self.rescan()

    def chosen(self) -> str:
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else ""


class ServerPage(Page):
    title = "服务器与发布"

    def __init__(self, dlg):
        super().__init__(dlg)
        self.head("服务器与发布", "这一屏可以整个跳过，之后在设置里补也一样。")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        self.ed_host = QLineEdit(settings.get("server_host"))
        self.ed_host.setPlaceholderText("IP 或 ~/.ssh/config 别名；留空 = blog-server")
        grid.addWidget(QLabel("服务器地址"), 0, 0)
        grid.addWidget(self.ed_host, 0, 1, 1, 2)

        self.ed_key = QLineEdit(settings.get("ssh_key"))
        self.ed_key.setPlaceholderText("私钥文件路径；留空 = ~/.ssh 里的默认密钥")
        grid.addWidget(QLabel("SSH 密钥"), 1, 0)
        grid.addWidget(self.ed_key, 1, 1)
        kb = QHBoxLayout()
        kb.setContentsMargins(0, 0, 0, 0)
        kb.addWidget(self._btn("浏览…", self._pick_key))
        grid.addLayout(kb, 1, 2)

        self.ed_pass = QLineEdit(settings.get("ssh_pass"))
        self.ed_pass.setEchoMode(QLineEdit.Password)
        self.ed_pass.setPlaceholderText("只做记录；免密请把密钥 ssh-add 到 agent")
        grid.addWidget(QLabel("密钥密码"), 2, 0)
        grid.addWidget(self.ed_pass, 2, 1, 1, 2)

        self.chk_proxy = QCheckBox("允许代理（连 GitHub 用）")
        self.chk_proxy.setChecked(settings.get("allow_proxy") == "1")
        grid.addWidget(self.chk_proxy, 3, 1, 1, 2)
        self.v.addLayout(grid)

        row = QHBoxLayout()
        self.btn_test = QPushButton("测试连接")
        self.btn_test.clicked.connect(self.test)
        row.addWidget(self.btn_test)
        self.result = QLabel("")
        row.addWidget(self.result, 1)
        self.v.addLayout(row)
        self.v.addStretch(1)

    def _btn(self, text, fn):
        b = QPushButton(text)
        b.clicked.connect(fn)
        return b

    def _pick_key(self):
        start = str(Path.home() / ".ssh")
        f, _ = QFileDialog.getOpenFileName(self, "选私钥", start, "密钥文件 (*)")
        if f:
            self.ed_key.setText(f)

    def test(self):
        from PySide6.QtCore import QProcess
        host = self.ed_host.text().strip() or "blog-server"
        key = self.ed_key.text().strip()
        args = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=6"]
        if key:
            args += ["-i", key, "-o", "IdentitiesOnly=yes"]
        args += [host, "true"]
        self.btn_test.setEnabled(False)
        self.result.setText("连接中…")
        self.result.setStyleSheet("color:gray; background:transparent;")
        self._proc = QProcess(self)
        self._proc.setProgram(remote.SSH_EXE)
        self._proc.setArguments(args)
        self._proc.finished.connect(self._tested)
        self._proc.start()

    def _tested(self, code, _status):
        self.btn_test.setEnabled(True)
        if code == 0:
            self.result.setText("✓ 连上了")
            self.result.setStyleSheet("color:" + VER_OK + "; background:transparent;")
        else:
            err = bytes(self._proc.readAllStandardError().data()).decode("utf-8", "replace").strip()
            self.result.setText("✗ 连不上：" + (err.splitlines()[-1] if err else "退出码 %d" % code))
            self.result.setStyleSheet("color:" + VER_BAD + "; background:transparent;")


class LookPage(Page):
    title = "外观"

    THEMES = [("auto", "跟随系统"), ("dark-black", "深色（黑）"), ("dark-blue", "深色（蓝）"),
              ("light-cool", "浅色（冷）"), ("light-beige", "浅色（米黄）")]

    def __init__(self, dlg):
        super().__init__(dlg)
        self.head("外观", "点一下整个窗口立刻换肤，满意再继续。")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.group = QButtonGroup(self)
        self.buttons = {}
        current = settings.get("theme") or "auto"
        for tid, name in self.THEMES:
            b = QPushButton(name)
            b.setCheckable(True)
            b.setMinimumWidth(110)
            b.setChecked(tid == current)
            b.clicked.connect(lambda _=False, t=tid: self.pick(t))
            self.group.addButton(b)
            self.buttons[tid] = b
            row.addWidget(b)
        row.addStretch(1)
        self.v.addLayout(row)

        fams = []
        try:
            fams = sorted({f for f in QFontDatabase.families() if f})
        except Exception:
            pass
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        self.fonts = {}
        for i, (key, label) in enumerate((("ui_font", "正文"), ("mono_font", "代码"))):
            cb = QComboBox()
            bundled = theme.BUNDLED_UI if key == "ui_font" else theme.BUNDLED_MONO
            cb.addItem("默认（" + bundled + "）", "")
            for f in fams:
                cb.addItem(f, f)
            j = cb.findData(settings.get(key))
            cb.setCurrentIndex(max(0, j) if settings.get(key) else 0)
            self.fonts[key] = cb
            grid.addWidget(QLabel(label), i, 0)
            grid.addWidget(cb, i, 1)
            reset = QPushButton("回到默认")
            reset.clicked.connect(lambda _=False, c=cb: c.setCurrentIndex(0))
            grid.addWidget(reset, i, 2)
        self.v.addLayout(grid)
        self.v.addStretch(1)

    def pick(self, tid):
        from PySide6.QtWidgets import QApplication
        try:
            theme.apply(QApplication.instance(), theme.resolve(tid))
            self.dlg.restyle()
        except Exception:
            pass

    def chosen_theme(self) -> str:
        for tid, b in self.buttons.items():
            if b.isChecked():
                return tid
        return "auto"

    def font_value(self, key) -> str:
        return self.fonts[key].currentData() or ""


class CreditsPage(Page):
    title = "开源与致谢"

    def __init__(self, dlg):
        super().__init__(dlg)
        self.head("开源与致谢", "这个程序以 GPL-3.0 开源，站在这些项目肩上：")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        for i, (name, url, lic, icon, color) in enumerate(licenses.PROJECTS):
            cell = QWidget()
            cell.setObjectName("OobeCredit")
            h = QHBoxLayout(cell)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(8)
            b = QLabel()
            b.setPixmap(badges.badge(icon, color, 38, name))
            b.setFixedSize(38, 38)
            b.setToolTip(url)
            tv = QVBoxLayout()
            tv.setSpacing(0)
            n = QLabel(name)
            n.setObjectName("OobeCreditName")
            l = QLabel(lic)
            l.setObjectName("OobeFix")
            tv.addWidget(n)
            tv.addWidget(l)
            h.addWidget(b)
            h.addLayout(tv, 1)
            grid.addWidget(cell, i // 3, i % 3)
        self.v.addLayout(grid)

        row = QHBoxLayout()
        btn = QPushButton("查看完整许可证")
        btn.clicked.connect(self._open)
        row.addWidget(btn)
        row.addWidget(badges.gpl_badge(26))
        tip = QLabel("GPL-3.0：免费用、改、分发；发布修改版要同样开源")
        tip.setObjectName("OobeFix")
        row.addWidget(tip, 1)
        self.v.addLayout(row)

        self.ack = QCheckBox("我已阅读并了解上面这些项目的许可证")
        self.ack.toggled.connect(self._ack_changed)
        self.v.addWidget(self.ack)
        self.v.addStretch(1)

    def _ack_changed(self, on: bool):
        if hasattr(self.dlg, "btn_next"):
            self.dlg.btn_next.setEnabled(on)

    def can_advance(self) -> bool:
        return bool(getattr(self, "ack", None) and self.ack.isChecked())

    def _open(self):
        from .about import LicenseDialog
        LicenseDialog(self.dlg).exec()


class DonePage(Page):
    title = "完成"

    def __init__(self, dlg):
        super().__init__(dlg)
        self.v.setContentsMargins(24, 8, 24, 24)
        self.v.addStretch(1)
        big = QLabel()
        big.setPixmap(icons.fa_pixmap("circle-check", 72, theme.c()["good"]))
        big.setFixedSize(72, 72)
        self.big = big
        self.v.addWidget(big, 0, Qt.AlignHCenter)
        t = QLabel("都搞定了")
        t.setObjectName("OobeHeroBig")
        self.v.addWidget(t, 0, Qt.AlignHCenter)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setAlignment(Qt.AlignHCenter)
        self.summary.setObjectName("OobeSummary")
        self.v.addWidget(self.summary, 0, Qt.AlignHCenter)
        self.v.addStretch(1)
        self.confetti = Confetti(self)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.confetti.setGeometry(self.rect())

    def on_enter(self):
        b = self.dlg.blog_page.blog_dir()
        self.summary.setText(
            "博客目录　%s" % (b if self.dlg.blog_page.ed.text().strip() else str(b) + "（默认）")
            + chr(10) + "主题配置　" + (self.dlg.theme_page.chosen() or "默认路径")
            + chr(10) + "服务器　　" + (self.dlg.server_page.ed_host.text().strip() or "blog-server（默认）")
            + chr(10) + "外　　观　" + dict(LookPage.THEMES).get(self.dlg.look_page.chosen_theme(), "")
        )
        self.confetti.celebrate()
        pop_in(self.big, 72)


    def hideEvent(self, e):
        super().hideEvent(e)
        self.confetti.stop()


class OobeDialog(QDialog):
    """六步引导。第一次启动时弹，也可以从设置里重跑。"""

    STEPS = ["欢迎与环境", "许可协议", "博客目录", "主题配置", "服务器与发布", "外观", "开源与致谢", "完成"]

    completed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("开始使用 · " + APP_TITLE)
        self.setMinimumSize(1040, 700)
        self.RAIL_W = 268
        from PySide6.QtGui import QGuiApplication
        scr = QGuiApplication.primaryScreen()
        if scr is not None:
            geo = scr.availableGeometry()
            w = max(1040, min(1180, int(geo.width() * 0.88)))
            h = max(700, min(820, int(geo.height() * 0.90)))
            self.resize(w, h)
            self.move(geo.center() - self.rect().center())
        else:
            self.resize(1120, 760)
        self.skipped = False
        self.aborted = False
        self._finished = False
        self.cur = 0
        self._build()
        self.restyle()
        self._go(0, animate=False)
        QTimer.singleShot(150, self.welcome.run_checks)

    # ── 界面 ──
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        rail = QWidget()
        rail.setObjectName("OobeRail")
        rail.setFixedWidth(self.RAIL_W)
        rv = QVBoxLayout(rail)
        rv.setContentsMargins(20, 20, 16, 20)
        rv.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icons.fox_logo(30))
        logo.setFixedSize(30, 30)
        brand.addWidget(logo)
        name = QLabel(APP_TITLE)
        name.setObjectName("OobeBrand")
        brand.addWidget(name, 1)
        rv.addLayout(brand)
        self.prog = QWidget()
        self.prog.setFixedHeight(3)
        self.prog.setMaximumWidth(1)
        rv.addSpacing(8)
        rv.addWidget(self.prog)
        rv.addSpacing(8)

        self.step_items = []
        for i, text in enumerate(self.STEPS):
            row = QWidget()
            row.setObjectName("OobeStepRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 2, 0, 2)
            h.setSpacing(10)
            num = QLabel(str(i + 1))
            num.setFixedSize(24, 24)
            num.setAlignment(Qt.AlignCenter)
            t = QLabel(text)
            h.addWidget(num)
            h.addWidget(t, 1)
            rv.addWidget(row)
            self.step_items.append((num, t))
        rv.addStretch(1)
        tip = QLabel("之后可以在设置里重新运行引导")
        tip.setObjectName("OobeRailTip")
        tip.setWordWrap(True)
        rv.addWidget(tip)

        rv.addSpacing(8)
        self.rail_badge = badges.gpl_badge(36)
        rv.addWidget(self.rail_badge, 0, Qt.AlignLeft)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        self.stage = Stage(self)
        sl = QVBoxLayout(self.stage)
        sl.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        self.welcome = WelcomePage(self)
        self.eula_page = EulaPage(self)
        self.blog_page = BlogPage(self)
        self.theme_page = ThemePage(self)
        self.server_page = ServerPage(self)
        self.look_page = LookPage(self)
        self.credits_page = CreditsPage(self)
        self.done_page = DonePage(self)
        for pg in (self.welcome, self.eula_page, self.blog_page, self.theme_page,
                   self.server_page, self.look_page, self.credits_page, self.done_page):
            self.stack.addWidget(pg)
        sl.addWidget(self.stack)
        right.addWidget(self.stage, 1)

        foot = QWidget()
        foot.setObjectName("OobeFoot")
        fh = QHBoxLayout(foot)
        fh.setContentsMargins(20, 10, 20, 14)
        fh.setSpacing(8)
        self.btn_skip = QPushButton("跳过")
        self.btn_skip.clicked.connect(self._skip)
        self.btn_back = QPushButton("上一步")
        self.btn_back.clicked.connect(self._back)
        self.btn_next = QPushButton("下一步")
        self.btn_next.setObjectName("Primary")
        self.btn_next.clicked.connect(self._next)
        fh.addWidget(self.btn_skip)
        fh.addStretch(1)
        fh.addWidget(self.btn_back)
        fh.addWidget(self.btn_next)
        right.addWidget(foot)

        root.addWidget(rail)
        root.addLayout(right, 1)

    def _fit_aurora(self):
        pass

    def page(self) -> Page:
        return self.stack.currentWidget()

    def restyle(self):
        p = theme.c()
        self.setStyleSheet(
            "QDialog { background: " + p["bg"] + "; }"
            "#OobeRail { background: " + p["surface"] + "; border-right: 1px solid " + p["line"] + "; }"
            "#OobeRailTip { color: " + p["ink2"] + "; font-size: 11.5px; background: transparent; }"
            "#OobeBrand { color: " + p["ink"] + "; font-size: 13px; font-weight: 600; background: transparent; }"
            "#OobeFoot { background: " + p["surface"] + "; border-top: 1px solid " + p["line"] + "; }"
            "#OobeHero { font-size: 22px; font-weight: 700; color: " + p["ink"] + "; background: transparent; }"
            "#OobeHeroBig { font-size: 28px; font-weight: 700; color: " + p["ink"] + "; background: transparent; }"
            "#OobeSummary { font-size: 13px; color: " + p["ink2"] + "; background: transparent; }"
            "#OobeTitle { font-size: 16px; font-weight: 600; color: " + p["ink"] + "; background: transparent; }"
            "#OobeSub { color: " + p["ink2"] + "; background: transparent; }"
            "#OobeStatus { color: " + p["ink2"] + "; background: transparent; }"
            "#OobeFix { color: " + p["ink2"] + "; font-size: 12px; background: transparent; }"
            "QStackedWidget { background: transparent; }"
            "QLabel { background: transparent; }"
            "#OobeStepRow { background: transparent; }"
            "#OobeCredit { background: transparent; }"
            "#OobeCreditName { font-size: 12.5px; color: " + p["ink"] + "; background: transparent; }"
            "#EulaBox { background: " + p["panel"] + "; border: 1px solid " + p["line"] + "; border-radius: 8px; }"
        )
        self._refresh_rail()

    def _refresh_rail(self):
        p = theme.c()
        self.prog.setStyleSheet("background:" + p["accent"] + "; border-radius:1px;")
        target = int((self.RAIL_W - 40) * (self.cur + 1) / max(1, len(self.STEPS)))
        a = QPropertyAnimation(self.prog, b"maximumWidth", self.prog)
        a.setDuration(260)
        a.setStartValue(max(1, self.prog.maximumWidth()))
        a.setEndValue(target)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.start(QAbstractAnimation.DeleteWhenStopped)
        for i, (num, t) in enumerate(self.step_items):
            if i < self.cur:
                num.setText("✓")
                num.setStyleSheet(
                    "background:" + p["accent_soft"] + "; color:" + p["accent"] + ";"
                    " border-radius:11px; font-size:13px; font-weight:700;")
                t.setStyleSheet("color:" + p["ink2"] + "; font-size:14.5px; background:transparent;")
            elif i == self.cur:
                num.setText(str(i + 1))
                num.setStyleSheet(
                    "background:" + p["accent"] + "; color:#ffffff;"
                    " border-radius:11px; font-size:13px; font-weight:700;")
                t.setStyleSheet(
                    "color:" + p["ink"] + "; font-size:14.5px; font-weight:600; background:transparent;")
            else:
                num.setText(str(i + 1))
                num.setStyleSheet(
                    "background:" + p["chip"] + "; color:" + p["ink2"] + ";"
                    " border-radius:11px; font-size:13px;")
                t.setStyleSheet("color:" + p["ink2"] + "; font-size:14.5px; background:transparent;")

    # ── 步骤切换（带淡入动画）──
    def _go(self, i, animate=True):
        from PySide6.QtCore import QAbstractAnimation
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        i = max(0, min(i, self.stack.count() - 1))
        # 切换前把残留的透明度特效摘掉：特效 + 换肤同时生效容易把界面搞崩
        for k in range(self.stack.count()):
            w = self.stack.widget(k)
            if w is not None and w.graphicsEffect() is not None:
                w.setGraphicsEffect(None)
        self.cur = i
        self.stack.setCurrentIndex(i)
        if animate:
            pg = self.stack.currentWidget()
            eff = QGraphicsOpacityEffect(pg)
            pg.setGraphicsEffect(eff)
            a = QPropertyAnimation(eff, b"opacity", pg)
            a.setDuration(200)
            a.setStartValue(0.0)
            a.setEndValue(1.0)
            a.setEasingCurve(QEasingCurve.OutCubic)

            def done():
                pg.setGraphicsEffect(None)

            a.finished.connect(done)
            a.start(QAbstractAnimation.DeleteWhenStopped)
        self._refresh_rail()
        self.btn_back.setEnabled(i > 0)
        self.btn_skip.setVisible(i < self.stack.count() - 1)
        self.btn_next.setText("完成" if i == self.stack.count() - 1 else "下一步")
        pg = self.stack.currentWidget()
        can = pg.can_advance() if hasattr(pg, "can_advance") else True
        self.btn_next.setEnabled(bool(can))
        if hasattr(pg, "on_enter"):
            pg.on_enter()

    def _next(self):
        if self.cur == self.stack.count() - 1:
            self._finish()
            return
        ok, msg = self.page().validate()
        if not ok:
            self.page().msg.setText("✗ " + msg) if hasattr(self.page(), "msg") else None
            return
        self._go(self.cur + 1)

    def _back(self):
        self._go(self.cur - 1)

    def reject(self):
        if self._finished or self.skipped:
            return super().reject()
        import os
        if os.environ.get("ND_SILENT") != "1":
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "引导没有完成",
                "还没有按步骤走完引导。" + chr(10) + chr(10)
                + "如果暂时不想配置，点「跳过」可以进入程序；直接关闭会退出程序。")
        self.aborted = True
        super().reject()

    def closeEvent(self, e):
        if self._finished or self.skipped:
            e.accept()
            return
        e.ignore()
        self.reject()

    def _skip(self):
        settings.put("oobe_skipped", "1")
        self.skipped = True
        self.reject()

    def _finish(self):
        settings.put("blog", self.blog_page.ed.text().strip())
        settings.put("config", self.theme_page.chosen())
        settings.put("theme", self.look_page.chosen_theme())
        settings.put("ui_font", self.look_page.font_value("ui_font"))
        settings.put("mono_font", self.look_page.font_value("mono_font"))
        settings.put("server_host", self.server_page.ed_host.text().strip())
        settings.put("ssh_key", self.server_page.ed_key.text().strip())
        settings.put("ssh_pass", self.server_page.ed_pass.text())
        settings.put("allow_proxy", "1" if self.server_page.chk_proxy.isChecked() else "0")
        self._finished = True
        settings.put("eula_ok", eula.EULA_VERSION)
        settings.put("oobe_done", "1")
        # 通知外面先把主窗口建起来（会应用刚保存的设置），再淡出自己，衔接成一次过渡
        self.completed.emit()
        self._fade_out_close()

    def _fade_out_close(self):
        a = QPropertyAnimation(self, b"windowOpacity", self)
        a.setDuration(240)
        a.setStartValue(1.0)
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.InCubic)
        a.finished.connect(self.close)
        a.start(QAbstractAnimation.DeleteWhenStopped)

    @staticmethod
    def should_show() -> bool:
        return not settings.get("oobe_done") and not settings.get("oobe_skipped")

