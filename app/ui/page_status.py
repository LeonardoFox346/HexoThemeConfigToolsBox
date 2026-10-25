"""服务器状态页。

分三块：
  · 代理四路检查 —— 上服务器前必须先看这里；
  · 服务器只读采集 —— 内存/磁盘/证书/fail2ban/最后部署/今日请求；
  · 采不到就明说原因，不硬连（有代理时连过去会触发异地登录告警）。

采集放在线程里，界面不卡。
"""
from __future__ import annotations

import os
import re
from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import remote, theme
from . import anim


class Ring(QWidget):
    """环形进度图：中心百分比，上方标题，下方明细。"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.percent = 0.0
        self.detail = ""
        self.tone = "ok"
        self.setMinimumSize(126, 112)

    def set_value(self, percent: float, detail: str = "", tone: str = "ok"):
        self.percent = max(0.0, min(100.0, percent))
        self.detail = detail
        self.tone = tone
        self.update()

    def paintEvent(self, event):
        p = theme.c()
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        side = min(w - 8, h - 40)
        if side < 40:
            return
        rect = QRectF((w - side) / 2.0, 20, side, side)

        pen = QPen(QColor(p["line"]), 9)
        pen.setCapStyle(Qt.RoundCap)
        g.setPen(pen)
        g.drawArc(rect, 0, 360 * 16)

        col = {"ok": p["good"], "warn": p["warn"], "bad": p["bad"]}.get(self.tone, p["accent"])
        pen = QPen(QColor(col), 9)
        pen.setCapStyle(Qt.RoundCap)
        g.setPen(pen)
        g.drawArc(rect, 90 * 16, -int(360 * 16 * self.percent / 100.0))

        f = QFont(theme.UI_FAMILY)
        f.setPointSizeF(14)
        f.setBold(True)
        g.setFont(f)
        g.setPen(QColor(p["ink"]))
        g.drawText(rect, Qt.AlignCenter, f"{self.percent:.0f}%")

        f2 = QFont(theme.UI_FAMILY)
        f2.setPointSizeF(9)
        g.setFont(f2)
        g.setPen(QColor(p["ink2"]))
        g.drawText(QRectF(0, 0, w, 18), Qt.AlignCenter, self.title)
        if self.detail:
            g.drawText(QRectF(0, h - 24, w, 22), Qt.AlignCenter, self.detail)


class _Worker(QThread):
    """采集线程。每个步骤都回传一行，界面上就是个滚动的终端。"""
    step = Signal(str)
    done = Signal(object)

    def __init__(self, with_server: bool):
        super().__init__()
        self.with_server = with_server

    def run(self):
        try:
            self.step.emit("$ 检查代理四路（进程 / 网卡 / 注册表 / 路由）")
            proxy = remote.proxy_check()
            for r in proxy:
                self.step.emit(f"    {'⚠ 命中' if r['hit'] else '✓ 通过'}  {r['name']}：{r['detail']}")

            server = None
            if self.with_server:
                if any(r["hit"] for r in proxy):
                    msg = "检测到代理正在生效，为避免触发服务器异地登录告警，本次不连接。"
                    server = (False, {}, msg)
                    self.step.emit("$ 有代理在生效 —— 放弃 ssh 连接")
                else:
                    self.step.emit(f"$ ssh {remote.host()} bash -s   （只读脚本 {len(remote.COLLECT_SH)} 字节）")
                    ok, data, msg = remote.collect(guard=False)   # 代理前面查过了
                    server = (ok, data, msg)
                    if ok:
                        for line in msg.splitlines():
                            if line.strip():
                                self.step.emit("  " + line.strip())
                    else:
                        self.step.emit("  ✗ " + msg.splitlines()[0])

            self.done.emit((proxy, server))
        except Exception as e:
            self.done.emit(([], (False, {}, f"采集异常：{e}")))


def _days_until(date_str: str) -> int | None:
    for fmt in ("%b %d %H:%M:%S %Y %Z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            s = date_str.strip()
            s = re.sub(r"\s+GMT.*$", " GMT", s)
            if fmt.endswith("%Z"):
                s = s.replace(" GMT", "")
                fmt2 = "%b %d %H:%M:%S %Y"
                d = datetime.strptime(s, fmt2)
            else:
                d = datetime.strptime(s, fmt)
            return (d - datetime.now()).days
        except Exception:
            continue
    return None


def _uptime_days(boot: str) -> str:
    try:
        d = datetime.strptime(boot.strip()[:19], "%Y-%m-%d %H:%M:%S")
        delta = datetime.now() - d
        return f"{delta.days} 天"
    except Exception:
        return "?"


class StatusPage(QWidget):
    def __init__(self, parent=None, open_settings=None):
        super().__init__(parent)
        self.open_settings = open_settings
        self.title = "服务器状态"
        self.status_tip = "全程只读，采完就断"
        self._thread: _Worker | None = None
        self._ignored_sig = ""      # 「忽略本次」只记住这一次的更新内容
        self._collected = False
        self._build()
        # 不自动采集 —— 每次进页面就 ssh 一次太浪费服务器资源，等用户点按钮
        self.hint.setText("点「开始采集」开始（只读，采完就断）")
        self.t_proxy.setRowCount(0)
        self.t_server.setRowCount(0)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn = QPushButton("开始采集")
        self.btn.setObjectName("Primary")
        self.btn.setFixedWidth(110)
        self.btn.clicked.connect(self.refresh)
        bar.addWidget(self.btn)

        self.spinner = anim.Spinner(self, 18)
        bar.addWidget(self.spinner)

        self.hint = QLabel("")
        self.hint.setStyleSheet(f"color: {theme.c()['ink2']}; background: transparent;")
        bar.addWidget(self.hint)
        bar.addStretch(1)
        self.lbl_target = QLabel(f"目标 {remote.host()}")
        self.lbl_target.setToolTip("当前 ssh 目标（设置里改了地址就是新的）")
        self.lbl_target.setStyleSheet(
            f"color: {theme.c()['ink2']}; background: transparent;")
        bar.addWidget(self.lbl_target)

        self.btn_settings = QPushButton("服务器设置…")
        self.btn_settings.setToolTip("服务器地址、SSH 密钥、密钥密码都在这里改")
        self.btn_settings.clicked.connect(
            lambda: self.open_settings() if self.open_settings else None)
        bar.addWidget(self.btn_settings)
        root.addLayout(bar)


        # 代理四路
        # 左右分列：左边「代理检查 + 执行终端」，右边「服务器结果 + 使用率」
        body = QHBoxLayout()
        body.setSpacing(12)

        # ── 左列 ──
        left = QVBoxLayout()
        left.setSpacing(5)

        left.addWidget(self._label("代理检查"))
        self.t_proxy = self._table(4)
        self.t_proxy.setMinimumHeight(30 * 5)
        left.addWidget(self.t_proxy)

        left.addWidget(self._label("执行过程"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(theme.mono_font(8.5))
        self._style_log()
        left.addWidget(self.log, 1)
        body.addLayout(left, 2)

        # ── 右列 ──
        right = QVBoxLayout()
        right.setSpacing(5)

        right.addWidget(self._label("服务器状态"))
        self.t_server = self._table(10)
        self.t_server.setMinimumHeight(30 * 9)
        right.addWidget(self.t_server, 1)

        right.addWidget(self._label("使用率"))
        grid = QGridLayout()
        grid.setSpacing(4)
        self.r_mem = Ring("内存")
        self.r_disk = Ring("磁盘")
        self.r_inode = Ring("inode")
        self.r_cert = Ring("证书剩余")
        grid.addWidget(self.r_mem, 0, 0)
        grid.addWidget(self.r_disk, 0, 1)
        grid.addWidget(self.r_inode, 1, 0)
        grid.addWidget(self.r_cert, 1, 1)
        right.addLayout(grid)
        body.addLayout(right, 3)

        root.addLayout(body, 1)

        self.note = QLabel("")
        self.note.setWordWrap(True)
        self.note.setStyleSheet(f"color: {theme.c()['ink2']};")
        root.addWidget(self.note)

    def _label(self, text: str) -> QLabel:
        lab = QLabel(text)
        f = QFont()
        f.setBold(True)
        lab.setFont(f)
        lab.setStyleSheet(f"color: {theme.c()['ink2']}; margin-top:6px;")
        return lab

    def _table(self, rows: int) -> QTableWidget:
        t = QTableWidget(rows, 2)
        t.setHorizontalHeaderLabels(["项目", "状态"])
        t.verticalHeader().setVisible(False)
        t.setShowGrid(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionMode(QTableWidget.NoSelection)
        t.verticalHeader().setDefaultSectionSize(34)
        hh = t.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        t.setColumnWidth(0, 210)
        return t

    # ── 采集 ──
    def refresh(self):
        if self._thread is not None and self._thread.isRunning():
            return
        self.btn.setEnabled(False)
        self.btn.setText("重新采集")
        self._collected = True
        self.spinner.start()
        self.hint.setText("采集中…")
        self.log.clear()
        self.log.appendPlainText("──── 开始采集 ────")
        self.t_server.setRowCount(0)
        self.note.setText("")
        self._thread = _Worker(with_server=True)
        self._thread.step.connect(self._on_step)
        self._thread.done.connect(self._show)
        self._thread.start()

    def _on_step(self, line: str):
        self.log.appendPlainText(line)
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _style_log(self):
        p = theme.c()
        self.log.setStyleSheet(
            f"background:{p['field']}; color:{p['ink2']};"
            f"border:1px solid {p['line']}; border-radius:8px; padding:6px;")

    def _check_updates(self, data: dict):
        """有更新就弹提醒。列出具体包名，「忽略本次」只对相同内容生效。"""
        if "UPDATES" not in data:
            return
        bits = data["UPDATES"].split()
        try:
            total = int(bits[0])
            sec = int(bits[1]) if len(bits) > 1 else 0
        except (ValueError, IndexError):
            return
        if total <= 0 and sec <= 0:
            return

        sec_pkgs = data.get("UPDSEC", "").split()
        all_pkgs = data.get("UPDPKG", "").split()

        # 签名 = 数量 + 安全包名。内容一变就会重新提醒
        sig = f"{total}|{sec}|{','.join(sec_pkgs)}|{len(all_pkgs)}"
        if sig == self._ignored_sig:
            return

        # 自动化测试用：设了这个环境变量就不弹模态框（否则会卡住事件循环）
        if os.environ.get("ND_NO_UPDATE_POPUP"):
            self.status_tip = f"有 {total} 个可用更新，其中 {sec} 个安全更新（弹窗已跳过）"
            return

        p = theme.c()
        box = QMessageBox(self)
        box.setWindowTitle("有可用更新")
        box.setIcon(QMessageBox.Warning if sec else QMessageBox.Information)
        box.setTextFormat(Qt.RichText)

        head = f"检测到 <b>{total}</b> 个可用更新"
        if sec:
            head += f"，其中 <b style='color:{p['bad']}'>{sec} 个安全更新</b>"
        box.setText(head)

        if sec_pkgs:
            box.setInformativeText("安全更新涉及：" + "、".join(sec_pkgs[:8]))
        else:
            box.setInformativeText("没有安全更新，可以找时间再升。")

        detail = []
        if sec_pkgs:
            detail.append("【安全更新】")
            detail.extend("  " + x for x in sec_pkgs)
            detail.append("")
        detail.append(f"【全部待更新 {len(all_pkgs)} 个】")
        detail.extend("  " + x for x in all_pkgs)
        detail.append("")
        detail.append("升级命令：sudo apt update && sudo apt upgrade")
        box.setDetailedText("\n".join(detail))

        btn_ignore = box.addButton("忽略本次", QMessageBox.RejectRole)
        btn_copy = box.addButton("复制升级命令", QMessageBox.ActionRole)
        btn_ok = box.addButton("知道了", QMessageBox.AcceptRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is btn_ignore:
            # 只忽略这一次：签名不变才不弹，出现新包还会提醒
            self._ignored_sig = sig
            self.status_tip = "已忽略本次更新提醒（有新包时会重新提醒）"
        elif clicked is btn_copy:
            QGuiApplication.clipboard().setText("sudo apt update && sudo apt upgrade")
            self.status_tip = "升级命令已复制到剪贴板"

    def _burn(self):
        """阅后即焚：原始输出只留来看执行过程，分析完就丢掉。"""
        QTimer.singleShot(1500, self._clear_log)

    def _clear_log(self):
        """清空终端，但留一行状态说明，免得用户以为它坏了。"""
        try:
            self.log.clear()
            self.log.appendPlainText("✓ 已执行完成　终端已清空")
        except RuntimeError:
            pass

    def _show(self, payload):
        proxy, server = payload
        p = theme.c()
        color = {"ok": p["good"], "warn": p["warn"], "bad": p["bad"], "info": p["ink2"]}

        # 代理
        self.t_proxy.setRowCount(len(proxy))
        for i, r in enumerate(proxy):
            a = QTableWidgetItem(r["name"])
            a.setForeground(QColor(p["ink"]))
            self.t_proxy.setItem(i, 0, a)
            b = QTableWidgetItem(("⚠ " if r["hit"] else "✓ ") + r["detail"])
            b.setForeground(QColor(p["bad"] if r["hit"] else p["good"]))
            self.t_proxy.setItem(i, 1, b)

        if server is None:
            self.spinner.stop()
            self.btn.setEnabled(True)
            self.hint.setText("完成")
            return

        ok, data, msg = server
        if not ok:
            self.t_server.setRowCount(1)
            a = QTableWidgetItem("采集未进行")
            a.setForeground(QColor(p["warn"]))
            self.t_server.setItem(0, 0, a)
            b = QTableWidgetItem(msg.split("\n")[0])
            b.setForeground(QColor(p["warn"]))
            self.t_server.setItem(0, 1, b)
            self.note.setText(msg)
            self.spinner.stop()
            self.btn.setEnabled(True)
            self.hint.setText("未采集（先关代理）")
            self._burn()
            return

        rows: list[tuple[str, str, str]] = []

        # 内存
        try:
            total, used, avail = (int(x) for x in data["MEM"].split())
            pct = used / total * 100 if total else 0
            sw = data.get("SWAP", "0 0").split()
            swap = sw[1] if len(sw) > 1 else "0"
            tone = "bad" if pct >= 90 else ("warn" if pct >= 75 else "ok")
            rows.append(("内存", f"{used} / {total} MB（{pct:.1f}%），可用 {avail} MB，swap {swap} MB", tone))
            self.r_mem.set_value(pct, f"{used}/{total} MB", tone)
        except Exception:
            pass

        if "DISK" in data:
            used, total = (data["DISK"].split() + ["?"])[:2]
            inode = data.get("INODE", "?")
            rows.append(("磁盘", f"{used} / {total}，inode {inode}", "ok"))
            try:
                nu = float(re.sub(r"[^\d.]", "", used)); nt = float(re.sub(r"[^\d.]", "", total))
                if nt:
                    dp = nu / nt * 100
                    self.r_disk.set_value(dp, f"{used} / {total}",
                                          "bad" if dp >= 90 else ("warn" if dp >= 75 else "ok"))
            except Exception:
                pass
            try:
                ip = float(inode.rstrip("%"))
                self.r_inode.set_value(ip, f"{inode}%",
                                       "bad" if ip >= 90 else ("warn" if ip >= 80 else "ok"))
            except Exception:
                pass

        # 系统版本
        if "OS" in data:
            _kern = data.get("KERNEL", "")
            rows.append(("系统", data["OS"] + (f"　内核 {_kern}" if _kern else ""), "info"))

        load = data.get("LOAD", "?")
        up = _uptime_days(data.get("BOOT", ""))
        ng = data.get("NGINX", "?")
        ng_ok = ng.strip() == "active"
        rows.append(("负载 / 运行时间", f"load {load}，已运行 {up}", "ok"))
        _ngver = data.get("NGINXVER", "")
        rows.append(("nginx", f"{_ngver + '　' if _ngver else ''}{'运行中' if ng_ok else ng}",
                     "ok" if ng_ok else "bad"))

        cert = data.get("CERT", "")
        if cert:
            d = _days_until(cert)
            if d is None:
                rows.append(("HTTPS 证书", cert, "info"))
            else:
                try:
                    iso = datetime.now().strftime("%Y-%m-%d")
                    from datetime import timedelta
                    end = (datetime.now() + timedelta(days=d)).strftime("%Y-%m-%d")
                except Exception:
                    end = "?"
                tone = "bad" if d <= 14 else ("warn" if d <= 30 else "ok")
                rows.append(("HTTPS 证书", f"{d} 天后到期（{end}）", tone))
                self.r_cert.set_value(max(0.0, min(100.0, d / 365 * 100)), f"{d} 天", tone)
        else:
            rows.append(("HTTPS 证书", "读不到证书文件", "warn"))

        f2b = data.get("F2B")
        if isinstance(f2b, dict) and f2b:
            total = sum(f2b.values())
            jails = "、".join(f2b.keys())
            _f2bver = data.get("F2BVER", "")
            rows.append(("fail2ban",
                         f"{_f2bver + '　' if _f2bver else ''}当前封禁 {total} 个 IP，jail = {jails}",
                         "ok" if total == 0 else "warn"))

        if "UPDATES" in data:
            _ub = data["UPDATES"].split()
            _tot = _ub[0] if _ub else "0"
            _sec = _ub[1] if len(_ub) > 1 else "0"
            try:
                _secn = int(_sec)
            except ValueError:
                _secn = 0
            if _secn > 0:
                rows.append(("待更新", f"{_tot} 个可用更新，其中 {_secn} 个安全更新",
                             "bad" if _secn >= 5 else "warn"))
            else:
                rows.append(("待更新", f"{_tot} 个可用更新，无安全更新", "ok"))

        if "DEPLOY" in data:
            rows.append(("最后部署", data["DEPLOY"], "info"))
        if "DEPLOYMSG" in data:
            rows.append(("提交说明", data["DEPLOYMSG"][:70], "info"))
        if "REQ" in data:
            bits = data["REQ"].split()
            total = bits[0] if bits else "?"
            bad = bits[1] if len(bits) > 1 else "?"
            rows.append(("今日请求", f"{total}，4xx/5xx {bad}",
                         "ok" if bad in ("0", "?") else "warn"))

        self.t_server.setRowCount(len(rows))
        for i, (name, val, tone) in enumerate(rows):
            a = QTableWidgetItem(name)
            a.setForeground(QColor(p["ink"]))
            f = QFont()
            f.setBold(True)
            a.setFont(f)
            self.t_server.setItem(i, 0, a)
            b = QTableWidgetItem(val)
            b.setForeground(QColor(color.get(tone, p["ink2"])))
            self.t_server.setItem(i, 1, b)

        self.spinner.stop()
        self.btn.setEnabled(True)
        self.hint.setText(f"采集完成 · {datetime.now():%H:%M:%S}")
        self._check_updates(data)
        self._burn()
        self.note.setText("")

    def apply_theme(self):
        p = theme.c()
        self.hint.setStyleSheet(f"color: {p['ink2']};")
        self.note.setStyleSheet(f"color: {p['ink2']};")
        self._style_log()          # 终端是按当时配色写死的内联样式，换肤要重刷
        for ring in (self.r_mem, self.r_disk, self.r_inode, self.r_cert):
            ring.update()
        for table in (self.t_proxy, self.t_server):
            table.viewport().update()
