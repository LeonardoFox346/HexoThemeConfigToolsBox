"""Markdown → HTML，供 QWebEngineView 做「样式预览」。

为什么不用 QTextBrowser.setMarkdown：它对内联 HTML 支持很差，
而这批文章里预置了大量 <div> / <style> / <details> 之类，setMarkdown 会吞掉或显示不全。
这里用 python-markdown 完整转换（允许内联 HTML），再套上主题的 index.css。
"""
from __future__ import annotations

from pathlib import Path

import markdown

from .paths import PUBLIC

_CSS_CACHE: dict[str, str] = {}
THEME_CSS = PUBLIC / "css" / "index.css"


def _css_href() -> str:
    try:
        if THEME_CSS.exists():
            return THEME_CSS.resolve().as_uri()
    except Exception:
        pass
    return ""


def convert(md_text: str) -> str:
    """Markdown → HTML 片段。允许内联 HTML，支持表格、代码块、目录。"""
    return markdown.markdown(
        md_text,
        extensions=[
            "extra",          # 含 tables / fenced_code / footnotes / attr_list
            "sane_lists",
            "toc",
            "admonition",
        ],
        output_format="html5",
    )


FALLBACK_CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 28px 34px 80px;
  background: #12161C; color: #E6EAF0;
  font-family: "Microsoft YaHei UI","Segoe UI",sans-serif;
  font-size: 15.5px; line-height: 1.85;
}
h1,h2,h3,h4,h5,h6 { line-height:1.35; margin:1.6em 0 .7em; font-weight:700; }
h1 { font-size:1.9em; } h2 { font-size:1.55em; } h3 { font-size:1.28em; }
h1,h2 { border-bottom:1px solid #262F3B; padding-bottom:.35em; }
a { color:#5B9DFF; text-decoration:none; }
a:hover { text-decoration:underline; }
p { margin:.85em 0; }
code {
  font-family:"JetBrains Mono","Consolas",monospace; font-size:.9em;
  background:#1B222C; border:1px solid #262F3B; border-radius:5px; padding:.12em .38em;
  color:#FBBF24;
}
pre {
  background:#161B22; border:1px solid #262F3B; border-radius:9px;
  padding:14px 16px; overflow:auto;
}
pre code { background:none; border:none; padding:0; color:#E6EAF0; font-size:.88em; }
blockquote {
  margin:1em 0; padding:.5em 1em; border-left:3px solid #5B9DFF;
  background:#1B222C; border-radius:0 7px 7px 0; color:#93A0B1;
}
table { border-collapse:collapse; margin:1.1em 0; width:100%; font-size:.95em; }
th,td { border:1px solid #262F3B; padding:8px 12px; text-align:left; }
th { background:#1B222C; font-weight:600; }
tr:nth-child(even) td { background:#171C24; }
img { max-width:100%; border-radius:8px; }
hr { border:none; border-top:1px solid #262F3B; margin:1.8em 0; }
ul,ol { padding-left:1.6em; }
li { margin:.3em 0; }
details { background:#1B222C; border:1px solid #262F3B; border-radius:8px; padding:8px 12px; margin:1em 0; }
summary { cursor:pointer; font-weight:600; }
.toc { background:#1B222C; border:1px solid #262F3B; border-radius:8px; padding:12px 18px; }
.toc ul { margin:.3em 0; }
"""


def page(md_text: str, *, use_theme_css: bool = True, dark: bool = True) -> str:
    """生成完整 HTML 文档。"""
    body = convert(md_text)
    href = _css_href() if use_theme_css else ""

    if href:
        # 套主题样式：anzhiyu 的文章主体在 #post .post-content 里。
        # 主题 CSS 是站点自己的亮/暗样式，这里一律按亮色底渲染 ——
        # 深色 App 里硬套深色底 + 浅色主题的文字颜色，会黑字黑底，看着就是「什么都没显示」。
        head = f'<link rel="stylesheet" href="{href}">'
        style = ""
        body_class = ""
        wrapper = ('<div id="post"><div id="article-container">'
                   f'<div class="post-content" id="article">{body}</div>'
                   '</div></div>')
    else:
        head = ""
        style = f"<style>{FALLBACK_CSS}</style>"
        body_class = ""
        wrapper = body

    return f"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{head}{style}
<style>
  /* 兜底：主题 CSS 没覆盖到时至少能看清 */
  html, body {{ background: {('#FFFFFF' if href else ('#12161C' if dark else '#FFFFFF'))}; }}
  body {{ overflow-x: hidden; }}
  ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
  ::-webkit-scrollbar-thumb {{ background: #333c48; border-radius: 5px; }}
  ::-webkit-scrollbar-track {{ background: transparent; }}
</style>
</head>
<body class="{body_class}">
{wrapper}
</body></html>"""
