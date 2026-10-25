"""构建与发布的命令封装。真正的执行交给页面里的 QProcess。"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import paths

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def node_exe() -> str:
    return shutil.which("node") or r"C:\Program Files\nodejs\node.exe"


def pwsh_exe() -> str:
    return shutil.which("pwsh") or r"C:\Program Files\PowerShell\7\pwsh.exe"


def build_cmd() -> tuple[str, list[str]]:
    """hexo clean —— 用本地 hexo-cli，不用 npx（受限环境会报 StandardOutputEncoding）。"""
    return node_exe(), [str(paths.HEXO_CLI), "clean"]


def generate_cmd() -> tuple[str, list[str]]:
    return node_exe(), [str(paths.HEXO_CLI), "generate"]


def publish_cmd(message: str = "", skip_backup=False, skip_proxy=False):
    args = ["-NoProfile", "-File", str(paths.PUBLISH_PS1), "-NoPause"]
    if message.strip():
        args += ["-Message", message.strip()]
    if skip_backup:
        args.append("-SkipBackup")
    if skip_proxy:
        args.append("-SkipProxyCheck")
    return pwsh_exe(), args


def github_push_cmd(message: str = ""):
    """只推 GitHub 仓库：add → commit（有改动才提交）→ push，不碰服务器。"""
    msg = (message or "").strip() or "post: 更新站点"
    msg = msg.replace("'", "''")
    key = ""
    try:
        from . import settings
        key = settings.get("github_key").strip()
    except Exception:
        key = ""
    prefix = f"$env:GIT_SSH_COMMAND='ssh -i \"{key}\"'; " if key else ""
    script = (
        prefix +
        "$ErrorActionPreference='Continue'; "
        f"Set-Location '{workdir()}'; "
        "git add -A; "
        "$changed = git status --porcelain; "
        "if ($changed) { "
        f"  git commit -m '{msg}'; "
        "  if ($LASTEXITCODE -ne 0) { Write-Host 'COMMIT FAILED'; exit 1 } } "
        "else { Write-Host '源码无改动，跳过提交' }; "
        "git push; "
        "if ($LASTEXITCODE -ne 0) { Write-Host 'PUSH FAILED'; exit 1 }; "
        "Write-Host 'PUSH DONE'"
    )
    return pwsh_exe(), ["-NoProfile", "-Command", script]


def worktree_dirty() -> tuple[bool, int, str]:
    """blog 工作树有没有未提交的改动。

    publish.ps1 备份那步会 `git add -A`，工作树是脏的话，这些改动会被一起提交进去。
    所以发布前必须让用户看见这件事。
    """
    try:
        p = subprocess.run(
            ["git", "-C", str(paths.BLOG), "status", "--porcelain"],
            capture_output=True, timeout=20, creationflags=NO_WINDOW)
        text = p.stdout.decode("utf-8", errors="replace")
        files = [ln for ln in text.splitlines() if ln.strip()]
        return bool(files), len(files), "\n".join(files[:10])
    except FileNotFoundError:
        return False, 0, "本机找不到 git 命令"
    except Exception as e:
        return False, 0, f"{type(e).__name__}: {e}"


def worktree_files():
    """列出未提交的改动，返回 [(状态码, 路径)]。状态码 M/A/D/?? 之类。"""
    try:
        p = subprocess.run(
            ["git", "-C", str(paths.BLOG), "status", "--porcelain"],
            capture_output=True, timeout=20, creationflags=NO_WINDOW)
        text = p.stdout.decode("utf-8", errors="replace")
        out = []
        for ln in text.splitlines():
            if not ln.strip():
                continue
            code = (ln[:2].strip() or "?")
            path = ln[3:].strip()
            if path:
                out.append((code, path))
        return out
    except Exception:
        return []


def last_publish_verdict() -> tuple[bool, str]:
    """读 publish.log 判定上一次发布是否真的成功。

    判据两处都要有（它们来源不同）：
      · `Deploy done` —— hexo-deployer-git 打印的，说明推送执行了；
      · `✅ 部署完成`  —— 服务器 post-receive 钩子回显的，说明服务器那边真的收下并部署了。
    只认前者会漏掉「推上去了但服务器没部署」的情况。
    """
    log = Path(paths.PUBLISH_LOG)
    if not log.exists():
        return False, "找不到 publish.log"
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return False, f"读不到 publish.log：{e}"

    has_deploy = "Deploy done" in text
    has_hook = "✅ 部署完成" in text
    if has_deploy and has_hook:
        m = [ln for ln in text.splitlines() if "部署完成" in ln]
        return True, (m[-1].strip() if m else "两处判据都命中")
    if has_deploy and not has_hook:
        return False, "有 Deploy done，但没看到服务器回显的「✅ 部署完成」——服务器那段可能没跑成"
    if has_hook and not has_deploy:
        return False, "有服务器回显，但没有 Deploy done —— 推送过程可能出问题了"
    return False, "两处判据都没找到，这次发布多半没成功"


def workdir() -> str:
    return str(paths.BLOG)

