"""导出 / 导入配置：一份可以直接再导入的 JSON + 一份填写说明。

用 JSON 而不是 ini：配置里有 hidden_pages / custom_pages 这种列表和字典，
ini 表达不了层级，JSON 存下来能原样导回去。
"""
from __future__ import annotations

import json

from . import paths, settings

SCALAR_KEYS = [
    "theme", "blog", "config", "ui_font", "mono_font",
    "server_host", "ssh_key", "ssh_pass", "github_repo", "github_key",
    "push_mode", "persist",
]


def build_export() -> tuple[str, str]:
    data = {k: settings.get(k) for k in SCALAR_KEYS}
    data["hidden_pages"] = settings.get_hidden_pages()
    data["custom_pages"] = settings.get_custom_pages()

    js = json.dumps(data, ensure_ascii=False, indent=2)
    md = """# 写作台配置说明

这份 JSON 可以直接用「设置 → 导入配置」导回去。逐项含义：

## 基础
- theme：外观。auto = 跟随系统；也可写 dark-blue / dark-black / light-cool / light-beige。
- blog：博客仓库根目录（里面有 source/_posts 和 _config.yml）。留空 = 默认目录。
- config：主题配置文件。留空 = <博客目录>/_config.anzhiyu.yml。

## 字体
- ui_font / mono_font：正文 / 代码字体。留空 = 自带思源黑体 / JetBrains Mono。

## 服务器（只读采集用）
- server_host：服务器 IP，或 ~/.ssh/config 里的别名（如 blog-server）。留空 = 内置别名。
- ssh_key：私钥路径。留空 = 走 ssh 默认（~/.ssh + agent）。
- ssh_pass：只做记录，ssh.exe 非交互模式不会读它；
  带密码短语的密钥先 ssh-add <私钥>，让 agent 记住。

## GitHub 与发布
- github_repo：owner/repo 或完整地址，仅记录与导出。
- github_key：GitHub 用的私钥路径。
- push_mode：both = 服务器 + GitHub 备份；server = 只推服务器（-SkipBackup）。

## 其它
- persist："1" = 退出后保留设置；"0" = 只在本次运行生效。
- hidden_pages：侧边栏隐藏的页面名，例如 ["装备", "相册"]。
- custom_pages：导入的 yml 页，每项 {name, file, icon}；file 写绝对路径最稳。

## 换机器
- 带着程序目录（fonts/、app.ico）和这份 JSON 即可；导入后博客目录 / 字体要重启生效。
"""
    return js, md


def apply_import(data: dict) -> int:
    """把导出的 JSON 写回设置，返回导入了多少项。"""
    if not isinstance(data, dict):
        return 0
    n = 0
    for k in SCALAR_KEYS:
        if k in data and data[k] is not None:
            settings.put(k, str(data[k]))
            n += 1
    hidden = data.get("hidden_pages")
    if isinstance(hidden, list):
        settings.set_hidden_pages([str(x) for x in hidden if str(x).strip()])
        n += 1
    pages = data.get("custom_pages")
    if isinstance(pages, list):
        clean = [p for p in pages
                 if isinstance(p, dict) and p.get("name") and p.get("file")]
        settings.set_custom_pages(clean)
        n += 1
    return n
