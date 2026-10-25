"""用户偏好：外观、博客目录、主题配置、字体、服务器、GitHub。

存在程序目录下的 settings.json（和 main.py 同级），跟程序一起拷走就能带走配置。
第一次启动时如果发现旧版本写在注册表里的值，会自动搬过来。
空字符串 = 用默认值（自带字体 / 默认博客目录 / 主题自带的 _config.anzhiyu.yml）。
"""
from __future__ import annotations

import json
from pathlib import Path

from .paths import USER_DIR

ROOT = USER_DIR
CONFIG_PATH = ROOT / "settings.json"

DEFAULTS = {
    "theme": "dark-blue",      # dark-blue / dark-black / light-cool / light-beige / auto
    "blog": "",                # 空 = 默认博客目录
    "config": "",              # 空 = <博客目录>/_config.anzhiyu.yml
    "ui_font": "",             # 空 = 自带思源黑体
    "mono_font": "",           # 空 = 自带 JetBrains Mono
    "server_host": "",         # 空 = 内置 blog-server（~/.ssh/config 别名）
    "ssh_key": "",             # 空 = ssh 默认（~/.ssh + agent）
    "ssh_pass": "",            # 只做记录；ssh.exe 非交互不会用它
    "github_repo": "",         # owner/repo 或 URL，仅记录与导出
    "github_key": "",          # GitHub 用的私钥路径
    "push_mode": "both",       # both = 服务器 + GitHub 备份；server = 只推服务器；github = 只推仓库
    "allow_proxy": "0",        # 1 = 允许代理（给要连 GitHub 的人）；服务器采集仍会被拦
    "persist": "1",            # 退出后是否把设置写回 settings.json
    "ed_preview": "1",        # 编辑器：同步预览
    "ed_style": "0",          # 编辑器：样式预览
    "ed_immersive": "0",      # 编辑器：沉浸
    "ed_sync": "1",           # 编辑器：同步滚动
    "data_dir": "",           # 五个 _data 文件所在文件夹（空 = <博客>/source/_data）
    "data_about": "",         # 单个文件覆盖（空 = <数据文件夹>/<默认名>）
    "data_equipment": "",
    "data_link": "",
    "data_album": "",
    "data_skills": "",
}

_cache: dict | None = None


def _migrate_from_registry() -> dict:
    """旧版把设置写在注册表里：第一次找不到 settings.json 时搬过来。"""
    data: dict = {}
    try:
        from PySide6.QtCore import QSettings
        s = QSettings("NardoFox", "BlogToolBox")
        for k in s.allKeys():
            v = s.value(k, "")
            data[k] = "" if v is None else str(v)
    except Exception:
        pass
    return data


def _write(data: dict):
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(CONFIG_PATH)
    except Exception:
        # 写不了就算了：内存里还有，别因为一个只读目录把界面搞崩
        pass


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    data: dict = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        migrated = _migrate_from_registry()
        if migrated:
            data = migrated
            _write(data)
    if not isinstance(data, dict):
        data = {}
    _cache = data
    return _cache


def get(key: str) -> str:
    v = _load().get(key, "")
    return "" if v is None else str(v)


def put(key: str, value: str):
    data = _load()
    data[key] = "" if value is None else str(value)
    if persist():
        _write(data)


def clear(keys):
    data = _load()
    for k in keys:
        data.pop(k, None)
    if persist():
        _write(data)


def persist() -> bool:
    """退出后要不要把设置写回文件（默认要）。"""
    v = _load().get("persist")
    if v is None:
        return True
    return str(v).lower() not in ("0", "false", "no", "")


def set_persist(on: bool):
    put("persist", "1" if on else "0")


def get_hidden_pages() -> list[str]:
    """侧边栏里要藏起来的页面名（装备 / 相册 / 技能）。"""
    raw = get("hidden_pages")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [x for x in data if isinstance(x, str)]
    except Exception:
        return []


def set_hidden_pages(names: list[str]):
    put("hidden_pages", json.dumps(list(dict.fromkeys(names)), ensure_ascii=False))


def get_custom_pages() -> list[dict]:
    """用户自己加的 yml 页：[{name, file, icon}]。"""
    raw = get("custom_pages")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [d for d in data if isinstance(d, dict) and d.get("name") and d.get("file")]
    except Exception:
        return []


def set_custom_pages(pages: list[dict]):
    put("custom_pages", json.dumps(pages, ensure_ascii=False))


def add_custom_page(entry: dict):
    pages = get_custom_pages()
    pages = [p for p in pages if p.get("file") != entry.get("file")]
    pages.append(entry)
    set_custom_pages(pages)
