"""本地/站点状态采集：站点可达性、代理开关、磁盘、进程。

代理检查是硬性要求 —— 上服务器前必须先确认代理已关（或已把服务器 IP 加进直连）。
这里同时查注册表代理和虚拟网卡名（mihomo / clash 的 TUN 常常只以网卡形式出现）。
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request

from .paths import BLOG

PROXY_HINTS = ("meta", "tunnel", "tap-", "clash", "mihomo", "v2ray", "wireguard", "wintun")


def site_ok(url: str, timeout: float = 6.0) -> tuple[bool, str, int]:
    """返回 (是否可达, 说明, 毫秒耗时)。"""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NardoDesk/2"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(1)
            ms = int((time.time() - t0) * 1000)
            return True, f"HTTP {r.status}", ms
    except urllib.error.HTTPError as e:
        ms = int((time.time() - t0) * 1000)
        return True, f"HTTP {e.code}", ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return False, f"{type(e).__name__}: {str(e)[:70]}", ms


def _reg_proxy() -> str:
    """注册表里的系统代理。"""
    try:
        import winreg
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        try:
            enable, _ = winreg.QueryValueEx(k, "ProxyEnable")
        except OSError:
            enable = 0
        try:
            server, _ = winreg.QueryValueEx(k, "ProxyServer")
        except OSError:
            server = ""
        return f"{server}" if int(enable) else ""
    except Exception:
        return ""


def _virtual_adapters() -> list[str]:
    """名称像代理软件的网卡。"""
    hits: list[str] = []
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetAdapter | Select-Object -ExpandProperty Name"],
            capture_output=True, timeout=12,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        text = out.stdout.decode("utf-8", errors="replace")
        for line in text.splitlines():
            name = line.strip()
            if not name:
                continue
            low = name.lower()
            if any(h in low for h in PROXY_HINTS):
                hits.append(name)
    except Exception:
        pass
    return hits


def proxy_state() -> tuple[bool, str]:
    """返回 (是否有代理在生效, 说明)。"""
    parts = []
    reg = _reg_proxy()
    if reg:
        parts.append(f"系统代理 {reg}")
    nets = _virtual_adapters()
    if nets:
        parts.append("虚拟网卡 " + "、".join(nets))
    if parts:
        return True, "；".join(parts)
    return False, "未发现系统代理或代理虚拟网卡"


def disk_free(path=BLOG) -> str:
    try:
        u = shutil.disk_usage(str(path))
        return f"{u.free / 1024 ** 3:.1f} GB 可用 / 共 {u.total / 1024 ** 3:.0f} GB"
    except Exception:
        return "读取失败"


def hexo_processes() -> int:
    """正在跑的 node 进程数（粗略判断有没有留在后台的 hexo）。"""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process node -ErrorAction SilentlyContinue | Measure-Object).Count"],
            capture_output=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return int(out.stdout.decode("utf-8", errors="replace").strip() or 0)
    except Exception:
        return 0


def local_port_open(port: int = 4173, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.8):
            return True
    except OSError:
        return False


def collect() -> list[tuple[str, str, str]]:
    """汇总成 (项目, 值, 状态) 列表，状态取值 ok / warn / bad / info。"""
    rows: list[tuple[str, str, str]] = []

    ok, msg, ms = site_ok("http://127.0.0.1:4173/")
    rows.append(("本地预览 4173", f"{msg}（{ms} ms）" if ok else "未启动（正常，构建后才有）",
                 "ok" if ok else "info"))

    has, desc = proxy_state()
    rows.append(("代理", desc, "bad" if has else "ok"))

    rows.append(("磁盘", disk_free(), "info"))
    rows.append(("后台 node 进程", f"{hexo_processes()} 个", "info"))
    rows.append(("发布时间", time.strftime("%Y-%m-%d %H:%M:%S"), "info"))
    return rows
