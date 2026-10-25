"""服务器只读采集 + 代理四路检查。

红线 R-PROXY / 「完全不动服务器」：
  · 采集方式是 ssh 跑一段**纯只读** bash，采完连接就断；
  · 不写文件、不开端口、不装东西、不留常驻进程。

必须用 Windows 自带 ssh.exe —— Git 附带的那个读不到 ssh-agent，
而服务器认证只认密钥且两把密钥都带密码短语，没有 agent 就必然 publickey 失败。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

SSH_EXE = r"C:\Windows\System32\OpenSSH\ssh.exe"
HOST = "blog-server"          # ~/.ssh/config 里的别名，含 Host/User/IdentityFile
# 不再内置任何真实 IP：解析不出来就跳过第④路检查，绝不用写死的地址兜底
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_ip_cache: dict[str, str] = {}


def _cfg(key: str) -> str:
    try:
        from . import settings
        return settings.get(key)
    except Exception:
        return ""


def host() -> str:
    """ssh 目标：设置里的地址（IP 或 ~/.ssh/config 别名），留空用内置别名。"""
    return _cfg("server_host") or HOST


def ssh_key() -> str:
    p = _cfg("ssh_key")
    return p if p and Path(p).exists() else ""


def server_ip() -> str:
    """给代理第 4 路检查用的 IP：地址本身是 IP 就用它，是别名就用 ssh -G 解析。"""
    h = host()
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", h):
        return h
    if h in _ip_cache:
        return _ip_cache[h]
    ip = ""
    try:
        p = subprocess.run([SSH_EXE, "-G", h], capture_output=True,
                           timeout=6, creationflags=NO_WINDOW)
        for line in p.stdout.decode("utf-8", "replace").splitlines():
            if line.lower().startswith("hostname "):
                ip = line.split(None, 1)[1].strip()
                break
    except Exception:
        ip = ""
    if not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", ip or ""):
        ip = ""
    _ip_cache[h] = ip
    return ip

# 纯只读巡检：每个指标一条命令，不作任何写入
COLLECT_SH = r"""
echo "HOST $(hostname)"
echo "BOOT $(uptime -s)"
echo "LOAD $(cut -d' ' -f1 /proc/loadavg)"
free -m | awk 'NR==2{printf "MEM %d %d %d\n", $2, $3, $7} /^Swap:/{printf "SWAP %d %d\n", $2, $3}'
df -h / | awk 'NR==2{printf "DISK %s %s\n", $3, $2}'
df -i / | awk 'NR==2{printf "INODE %s\n", $5}'
echo "NGINX $(systemctl is-active nginx 2>/dev/null || echo unknown)"
cert=$(ls -1 /etc/letsencrypt/live/*/fullchain.pem 2>/dev/null | head -n1)
if [ -r "$cert" ]; then
  echo "CERT $(openssl x509 -enddate -noout -in "$cert" 2>/dev/null | sed 's/notAfter=//')"
fi
for j in $(fail2ban-client status 2>/dev/null | sed -n 's/.*Jail list:[[:space:]]*//p' | tr ',' ' '); do
  n=$(fail2ban-client status "$j" 2>/dev/null | sed -n 's/.*Currently banned:[[:space:]]*//p')
  echo "F2B $j ${n:-0}"
done
# 部署仓库不写死路径：常见的裸仓库位置挨个试
repo=""
for d in /var/repo/*.git /opt/repo/*.git /srv/repo/*.git "$HOME"/*.git; do
  if [ -d "$d" ]; then repo="$d"; break; fi
done
if [ -n "$repo" ]; then
  ref="$repo/refs/heads/main"
  if [ -f "$ref" ]; then
    echo "DEPLOY $(stat -c %y "$ref" 2>/dev/null | cut -d. -f1)"
  else
    echo "DEPLOY $(git --git-dir="$repo" log -1 --format=%ci main 2>/dev/null)"
  fi
  echo "DEPLOYMSG $(git --git-dir="$repo" log -1 --format=%s main 2>/dev/null)"
fi
log=/var/log/nginx/access.log
today=$(date +%d/%b/%Y)
req=$(grep -c "$today" "$log" 2>/dev/null || echo 0)
bad=$(grep "$today" "$log" 2>/dev/null | awk -F'"' '{print $3}' | awk '{print $1}' | grep -cE '^[45]' || echo 0)
echo "REQ $req ${bad:-0}"
if [ -r /etc/os-release ]; then
  . /etc/os-release 2>/dev/null
  echo "OS ${PRETTY_NAME:-unknown}"
fi
echo "KERNEL $(uname -r)"
if command -v nginx >/dev/null 2>&1; then
  echo "NGINXVER $(nginx -v 2>&1 | sed 's#.*nginx/##')"
fi
if command -v fail2ban-client >/dev/null 2>&1; then
  echo "F2BVER $(fail2ban-client --version 2>/dev/null | head -1 | awk '{print $2}')"
fi
for c in php python3 node git; do
  if command -v $c >/dev/null 2>&1; then
    echo "VER_$c $($c --version 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)"
  fi
done
if [ -x /usr/lib/update-notifier/apt-check ]; then
  upd=$(timeout 25 /usr/lib/update-notifier/apt-check 2>&1 | tr ';' ' ')
  echo "UPDATES $upd"
fi
if command -v apt >/dev/null 2>&1; then
  _upd=$(timeout 25 apt list --upgradable 2>/dev/null | tail -n +2)
  echo "UPDPKG $(echo "$_upd" | cut -d/ -f1 | head -40 | tr '\n' ' ')"
  echo "UPDSEC $(echo "$_upd" | grep -i security | cut -d/ -f1 | head -20 | tr '\n' ' ')"
fi
"""


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def ssh_run(command: str = "bash -s", stdin: str = "", timeout: float = 30.0):
    """跑一条 ssh 命令。返回 (成功, stdout, stderr)。""" 
    args = [
        SSH_EXE,
        "-o", "BatchMode=yes",          # 绝不弹密码/确认框
        "-o", "ConnectTimeout=15",
    ]
    key = ssh_key()
    if key:
        args += ["-i", key, "-o", "IdentitiesOnly=yes"]
    args += [host(), command]
    try:
        p = subprocess.run(
            args,
            input=(stdin.encode("utf-8") if stdin else None),
            capture_output=True,
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
    except FileNotFoundError:
        return False, "", f"找不到 {SSH_EXE}"
    except subprocess.TimeoutExpired:
        return False, "", f"超时（{timeout:.0f} 秒）—— 多半是代理把连接吞了"
    except Exception as e:
        return False, "", f"{type(e).__name__}: {e}"

    out = _decode(p.stdout)
    err = _decode(p.stderr)
    if p.returncode != 0 and not out.strip():
        return False, out, err or f"退出码 {p.returncode}"
    return True, out, err


def collect(timeout: float = 70.0, guard: bool = True) -> tuple[bool, dict, str]:
    """采集服务器状态。返回 (成功, 指标, 原始输出或错误信息)。

    guard=True 时先做代理检查：命中就**根本不连**。
    带代理连过去会让服务器看到异地登录，云厂商通常会发异地登录告警 ——
    宁可少采一次，也不制造这个噪音。
    """
    if guard:
        hit, detail = proxy_blocking()
        if hit:
            return False, {}, (
                "检测到代理正在生效，为避免触发服务器异地登录告警，本次不连接。\n\n"
                + detail + "\n\n先把代理关掉（或把服务器地址 "
                + (server_ip() or host()) + " 加进直连），再重新采集。")

    ok, out, err = ssh_run("bash -s", COLLECT_SH, timeout=timeout)
    if not ok:
        return False, {}, (err or out).strip()

    data: dict[str, str] = {}
    f2b: dict[str, int] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        key = parts[0]
        val = parts[1].strip() if len(parts) > 1 else ""
        if key == "F2B":
            bits = val.split()
            if bits:
                try:
                    f2b[bits[0]] = int(bits[1]) if len(bits) > 1 else 0
                except ValueError:
                    f2b[bits[0]] = 0
        else:
            data[key] = val
    if f2b:
        data["F2B"] = f2b
    return True, data, out


# ══════════════ 代理四路检查 ══════════════
# 与 blog/publish.ps1 里的实现保持一致（进程 / 网卡 / 注册表 / 路由）

PROC_PATTERN = "mihomo|clash|verge|sing-box|v2ray|xray|shadowsocks|trojan|hysteria"
NET_PATTERN = "TUN|TAP|Mihomo|Clash|Meta|Sing|Wintun|WireGuard"
PROXY_NET_PATTERN = "TUN|TAP|Mihomo|Clash|Meta|Sing|Wintun|WireGuard|vEthernet"


def _ps(script: str, timeout: float = 15.0) -> str:
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
        return _decode(p.stdout).strip()
    except Exception:
        return ""


def proxy_check() -> list[dict]:
    """返回四路检查结果：[{name, hit, detail}]。

    第四路查的是「到服务器走哪块网卡」—— 只看注册表会漏掉 TUN 模式。
    """
    rows: list[dict] = []

    # ① 代理进程
    procs = _ps(f"(Get-Process | Where-Object {{ $_.ProcessName -match '{PROC_PATTERN}' }} | "
                f"Select-Object -ExpandProperty ProcessName -Unique) -join ','")
    rows.append({
        "name": "① 代理进程",
        "hit": bool(procs),
        "detail": procs if procs else "没有发现常驻代理进程",
    })

    # ② 虚拟网卡
    nets = _ps(f"(Get-NetAdapter | Where-Object {{ $_.Status -eq 'Up' -and "
               f"($_.Name -match '{NET_PATTERN}' -or $_.InterfaceDescription -match '{NET_PATTERN}') }} | "
               f"Select-Object -ExpandProperty Name) -join ','")
    rows.append({
        "name": "② 虚拟网卡",
        "hit": bool(nets),
        "detail": nets if nets else "没有处于 Up 状态的代理网卡",
    })

    # ③ 系统代理（注册表）
    reg = _ps("$k='HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings'; "
              "$e=(Get-ItemProperty $k -Name ProxyEnable -ErrorAction SilentlyContinue).ProxyEnable; "
              "$s=(Get-ItemProperty $k -Name ProxyServer -ErrorAction SilentlyContinue).ProxyServer; "
              "if($e -eq 1){ \"$s\" } else { '' }")
    rows.append({
        "name": "③ 系统代理",
        "hit": bool(reg),
        "detail": reg if reg else "ProxyEnable=0，未启用",
    })

    # ④ 到服务器的实际路由走哪块网卡（地址解析不出来就跳过，不用写死的 IP）
    ip = server_ip()
    if not ip:
        rows.append({
            "name": "④ 到服务器的路由",
            "hit": False,
            "detail": f"地址「{host()}」解析不出 IP，跳过这一路",
        })
        return rows
    route = _ps(f"(Find-NetRoute -RemoteIPAddress '{ip}' -ErrorAction SilentlyContinue | "
                f"Select-Object -First 1 -ExpandProperty InterfaceAlias)")
    hit4 = bool(route) and any(
        k in route for k in ("Meta", "TUN", "TAP", "Clash", "Mihomo", "Sing", "Wintun"))
    rows.append({
        "name": f"④ 到 {ip} 的路由",
        "hit": hit4,
        "detail": (f"走「{route}」" + ("　← 这是代理出口" if hit4 else "，直连")) if route else "查不到路由",
    })

    return rows


def proxy_blocking() -> tuple[bool, str]:
    """是否有代理会挡发布。返回 (是否命中, 命中详情)。"""
    rows = proxy_check()
    hits = [f"{r['name']}：{r['detail']}" for r in rows if r["hit"]]
    return bool(hits), "；".join(hits)
