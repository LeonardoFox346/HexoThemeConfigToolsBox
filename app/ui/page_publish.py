"""发布页：检查代理 / 构建 / 一键发布。

版面分四块：
  ① 本次更新说明（原样进 publish.ps1 -Message）
  ② 左：未提交的改动清单　右：当前状态（工作树 / 代理 / 上次发布判据）
  ③ 日志
  ④ 底部按钮

三处按 publish.ps1 的真实行为对齐：
  · 代理检查是**四路**（进程 / 网卡 / 注册表 / 到服务器的实际路由），任一路命中就拦；
  · 成功判据是**两处**：`Deploy done` 加上服务器钩子回显的 `✅ 部署完成`；
  · 发布前必须手输 YES 才算确认 —— 和 publish.ps1 交互时的口径一致。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from .. import publish, remote, settings, theme
from . import anim

CODE_LABEL = {
    "M": "修改", "A": "新增", "D": "删除", "R": "改名",
    "??": "未跟踪", "C": "复制", "U": "冲突",
}


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


class PublishPage(QWidget):
    def __init__(self, parent=None, open_settings=None):
        super().__init__(parent)
        self.open_settings = open_settings
        self.title = "发布"
        self.status_tip = "发布前必须手输 YES"
        self.proc: QProcess | None = None
        self._steps: list[tuple[str, list[str]]] = []
        self._is_publish = False
        self._is_github = (settings.get("push_mode") == "github")
        self._build()
        self.refresh_status()

    # ══════════════════ 界面 ══════════════════
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(9)

        # ② 中间：左改动清单 / 右状态，再和日志上下分
        vsplit = QSplitter(Qt.Vertical)
        vsplit.setChildrenCollapsible(False)
        vsplit.setHandleWidth(3)

        mid = QSplitter(Qt.Horizontal)
        mid.setChildrenCollapsible(False)
        mid.setHandleWidth(3)

        # 左：未提交的改动
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 6, 0)
        lv.setSpacing(4)

        self.lbl_changes = QLabel("未提交的改动")
        self.lbl_changes.setStyleSheet("font-weight: 600;")
        lv.addWidget(self.lbl_changes)

        self.list_changes = QListWidget()
        self.list_changes.setUniformItemSizes(True)
        self.list_changes.setWordWrap(False)
        self.list_changes.setSelectionMode(QAbstractItemView.NoSelection)
        self.list_changes.setFont(theme.mono_font(8.5))
        lv.addWidget(self.list_changes, 1)
        mid.addWidget(left)

        # 右：状态
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(6, 0, 0, 0)
        rv.setSpacing(6)

        head2 = QLabel("状态")
        head2.setStyleSheet("font-weight: 600;")
        rv.addWidget(head2)

        self.lbl_tree = QLabel("")
        self.lbl_tree.setWordWrap(True)
        rv.addWidget(self.lbl_tree)

        self.lbl_last = QLabel("")
        self.lbl_last.setWordWrap(True)
        rv.addWidget(self.lbl_last)

        self.btn_recheck = QPushButton("重新检查")
        self.btn_recheck.clicked.connect(self.refresh_status)
        rv.addWidget(self.btn_recheck)

        # 本次更新说明（放在「重新检查」下面）
        rv.addSpacing(10)
        p = theme.c()
        lab_msg = QLabel("本次更新了什么")
        lab_msg.setStyleSheet("font-weight: 600;")
        rv.addWidget(lab_msg)

        tip = QLabel("会成为源码备份仓库的提交说明，写清楚这次改了什么")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {p['ink2']}; font-size: 11px;")
        rv.addWidget(tip)

        self.msg = QLineEdit()
        self.msg.setPlaceholderText("例如：post: 新增 OLT 实训笔记　/　fix: 修首页公告卡指向")
        rv.addWidget(self.msg)

        rv.addStretch(1)
        mid.addWidget(right)

        mid.setSizes([460, 460])
        vsplit.addWidget(mid)

        # ③ 日志
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        f = QFont("JetBrains Mono", 9)
        f.setStyleHint(QFont.Monospace)
        self.log.setFont(f)
        self._style_log()
        vsplit.addWidget(self.log)
        vsplit.setSizes([280, 260])

        root.addWidget(vsplit, 1)

        # ④ 底部按钮
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.chk_backup = QCheckBox("跳过 GitHub 源码备份")
        self.chk_backup.setChecked(settings.get("push_mode") == "server")
        self.chk_backup.toggled.connect(
            lambda on: settings.put("push_mode", "server" if on else "both"))
        self.chk_proxy = QCheckBox("跳过代理检查（确认直连时）")
        self.chk_proxy.setChecked(settings.get("allow_proxy") == "1")
        if self._is_github:
            self.chk_backup.setChecked(False)
            self.chk_backup.setEnabled(False)
            self.chk_backup.setToolTip("当前是「只推 GitHub」模式，不涉及服务器备份开关")
        # 勾选项单独一行：按钮多了以后挤在一起，文字会被截
        chk_row = QHBoxLayout()
        chk_row.setSpacing(16)
        chk_row.addWidget(self.chk_backup)
        chk_row.addWidget(self.chk_proxy)
        chk_row.addStretch(1)
        root.addLayout(chk_row)

        row2.addStretch(1)

        self.btn_settings = QPushButton("设置…")
        self.btn_settings.setToolTip("服务器 / GitHub / 推送方式")
        self.btn_settings.clicked.connect(
            lambda: self.open_settings() if self.open_settings else None)
        row2.addWidget(self.btn_settings)

        self.btn_proxy = QPushButton("检查代理")
        self.btn_proxy.clicked.connect(self.check_proxy)
        self.btn_build = QPushButton("构建")
        self.btn_build.clicked.connect(self.build)
        self.btn_publish = QPushButton("一键发布")
        self.btn_publish.setObjectName("Primary")
        if self._is_github:
            self.btn_publish.setText("推送到 GitHub")
        self.btn_publish.clicked.connect(self.do_publish)
        for b in (self.btn_proxy, self.btn_build, self.btn_publish):
            b.setMinimumWidth(100)
            row2.addWidget(b)

        self.spinner = anim.Spinner(self, 18)
        row2.addWidget(self.spinner)
        root.addLayout(row2)

        self.state = QLabel("就绪")
        self.state.setStyleSheet(f"color: {theme.c()['ink2']};")
        root.addWidget(self.state)

    def _style_log(self):
        p = theme.c()
        self.log.setStyleSheet(
            f"background:{p['field']}; color:{p['ink']};"
            f"border:1px solid {p['line']}; border-radius:8px; padding:8px;")

    # ══════════════════ 状态刷新 ══════════════════
    def refresh_status(self):
        p = theme.c()
        files = publish.worktree_files()
        n = len(files)

        self.list_changes.clear()
        for code, path in files:
            label = CODE_LABEL.get(code, code)
            item = QListWidgetItem(f"{label}  {path}")
            item.setToolTip(f"{code}  {path}")
            self.list_changes.addItem(item)

        self.lbl_changes.setText(f"未提交的改动（{n}）")
        if n:
            self.lbl_changes.setStyleSheet(f"font-weight: 600; color: {p['warn']};")
            self.lbl_tree.setText(
                f"⚠ 有 {n} 处未提交改动。\n发布时备份那步会 `git add -A`，"
                f"这些改动会被一并提交进源码备份。")
            self.lbl_tree.setStyleSheet(f"color: {p['warn']};")
        else:
            self.lbl_changes.setStyleSheet("font-weight: 600;")
            self.lbl_tree.setText("✅ 工作树干净，发布时只会提交本次构建产生的变化。")
            self.lbl_tree.setStyleSheet(f"color: {p['good']};")

        good, detail = publish.last_publish_verdict()
        self.lbl_last.setText("上次发布：" + detail)
        self.lbl_last.setStyleSheet(f"color: {p['good'] if good else p['ink2']};")

    # ══════════════════ 日志 ══════════════════
    def say(self, text: str):
        self.log.appendPlainText(text.rstrip())
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_busy(self, busy: bool, text: str = ""):
        for b in (self.btn_proxy, self.btn_build, self.btn_publish, self.btn_recheck):
            b.setEnabled(not busy)
        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()
        self.state.setText(text or ("执行中…" if busy else "就绪"))

    # ══════════════════ 执行 ══════════════════
    def _run(self, program: str, args: list[str], title: str, is_publish=False):
        if self.proc is not None and self.proc.state() != QProcess.NotRunning:
            QMessageBox.information(self, "提示", "还有任务在跑，等它结束。")
            return
        self._is_publish = is_publish
        self.say(f"\n──── {title} ────")
        self.say("$ " + Path(program).name + " " + " ".join(args))
        self._set_busy(True, f"{title}…")

        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(publish.workdir())
        self.proc.readyReadStandardOutput.connect(self._on_out)
        self.proc.readyReadStandardError.connect(self._on_err)
        self.proc.finished.connect(lambda code, _s: self._on_done(code, title))
        self.proc.start(program, args)

    def _on_out(self):
        if self.proc:
            self.say(_decode(bytes(self.proc.readAllStandardOutput().data())))

    def _on_err(self):
        if self.proc:
            self.say(_decode(bytes(self.proc.readAllStandardError().data())))

    def _on_done(self, code: int, title: str):
        ok = (code == 0)
        self.say(f"──── {title} {'完成' if ok else '失败'}（退出码 {code}）────")
        self._set_busy(False, f"{title}{'完成' if ok else '失败'}")

        if ok and self._steps:
            self._run_next()
            return

        if self._is_publish:
            self._is_publish = False
            self.refresh_status()
            if ok and self._is_github:
                QMessageBox.information(self, "已推送", "源码已推送到 GitHub。\n\n"
                                        "GitHub Pages 的构建由仓库自己的 Actions / 分支设置负责。")
            elif ok:
                good, detail = publish.last_publish_verdict()
                self.say("\n判据核对：" + detail)
                if good:
                    QMessageBox.information(self, "发布成功", f"{detail}\n\n记得去站点上确认一下。")
                else:
                    QMessageBox.warning(self, "退出码是 0，但判据不全",
                                        f"{detail}\n\n别急着算成功，先看日志再确认站点。")
            else:
                anim.shake(self.window())
                QMessageBox.warning(self, "发布失败", f"退出码 {code}，把上面的日志发我。")

    # ══════════════════ 三个动作 ══════════════════
    def check_proxy(self):
        rows = remote.proxy_check()
        self.say("\n──── 代理四路检查 ────")
        hit = False
        for r in rows:
            mark = "⚠ 命中" if r["hit"] else "✓ 通过"
            self.say(f"  {r['name']}　{mark}　{r['detail']}")
            hit = hit or r["hit"]
        if hit:
            self.say("  → 有代理在生效。带代理发布会触发服务器异地登录告警，也可能连不上。")
            QMessageBox.warning(
                self, "检测到代理",
                "四路检查里有命中的（详见日志）。\n\n"
                f"上服务器前先把代理关掉，或把 {remote.server_ip() or remote.host()} "
                f"加进代理软件的直连规则。")
        else:
            self.say("  → 四路全部通过，可以发布。")

    def build(self):
        self.refresh_status()
        self._steps = [("清理", publish.build_cmd()), ("生成", publish.generate_cmd())]
        self._run_next()

    def _run_next(self):
        if not self._steps:
            self.say("\n构建全部完成。要生效还需要发布。")
            return
        title, (program, args) = self._steps.pop(0)
        self._run(program, args, title)

    def do_publish(self):
        if self.proc is not None and self.proc.state() != QProcess.NotRunning:
            QMessageBox.information(self, "提示", "还有任务在跑。")
            return

        if not self._is_github and not self.chk_proxy.isChecked():
            hit, detail = remote.proxy_blocking()
            if hit:
                QMessageBox.warning(self, "先关代理",
                                    f"代理检查有命中：\n{detail}\n\n"
                                    "请先关掉代理，或勾选「跳过代理检查」。")
                return

        # 先把改动清单列出来，再要求手输 YES
        files = publish.worktree_files()
        n = len(files)
        if self._is_github:
            lines = ["将执行：git add -A → commit → push 到 GitHub（不碰服务器）"]
        else:
            lines = ["将执行：清理 → 构建 → 部署到服务器"
                     + ("（跳过源码备份）" if self.chk_backup.isChecked()
                        else " → 源码备份到 GitHub")]
        if n:
            shown = "\n".join(f"  {CODE_LABEL.get(c, c):<4} {p}" for c, p in files[:8])
            more = f"\n  …… 还有 {n - 8} 个" if n > 8 else ""
            lines.append(f"\n⚠ 工作树有 {n} 处未提交改动，会被一起 git add -A 提交：\n{shown}{more}")
        lines.append("\n发布后线上会立刻变化。")

        text, ok = QInputDialog.getText(
            self, "确认发布",
            "\n".join(lines) + "\n\n确认请手动输入 YES（大写）：")
        if not ok:
            return
        if text.strip() != "YES":
            self.say("\n发布已取消：确认词不是 YES。")
            QMessageBox.information(self, "已取消", "确认词不是 YES，没有发布。")
            return

        if self._is_github:
            program, args = publish.github_push_cmd(self.msg.text())
            self._run(program, args, "推送到 GitHub", is_publish=True)
        else:
            program, args = publish.publish_cmd(
                self.msg.text(), self.chk_backup.isChecked(), self.chk_proxy.isChecked())
            self._run(program, args, "一键发布", is_publish=True)

    def apply_theme(self):
        self._style_log()
        self.state.setStyleSheet(f"color:{theme.c()['ink2']};")
        self.refresh_status()
