"""Markdown 快速插入菜单。

设计取自常用 Markdown 编辑器（Typora 那套右键菜单）：
格式 / 段落 / 列表 / 插入 四组，复制粘贴直接平铺在一级（不进子菜单）。
不设快捷键 —— 全部走右键，避免和系统输入法打架。
Front Matter 已有专门的解析，这里不重复提供。
"""
from __future__ import annotations

from PySide6.QtGui import QGuiApplication, QTextCursor
from PySide6.QtWidgets import QMenu

from .. import theme
from .icons import fa_icon

PLACEHOLDER = "文字"


def _i(name: str):
    """菜单图标。"""
    return fa_icon(name, 12)


# ── 基础动作 ──
def _sel_or_placeholder(editor) -> tuple[QTextCursor, str, bool]:
    cur = editor.textCursor()
    text = cur.selectedText().replace("\u2029", "\n")
    return cur, (text if text else PLACEHOLDER), bool(text)


def wrap(editor, before: str, after: str, placeholder: str = PLACEHOLDER):
    """把选中内容包起来；没选中就插入占位符并选中它，方便直接打字覆盖。"""
    cur, text, has_sel = _sel_or_placeholder(editor)
    if placeholder and text == PLACEHOLDER:
        text = placeholder
    cur.insertText(before + text + after)
    if not has_sel:
        start = cur.position() - len(after) - len(text)
        cur.setPosition(start)
        cur.setPosition(start + len(text), QTextCursor.KeepAnchor)
    editor.setTextCursor(cur)


def line_prefix(editor, prefix: str):
    """给当前行加前缀（标题、列表、引用都走这里）。"""
    cur = editor.textCursor()
    cur.beginEditBlock()
    cur.movePosition(QTextCursor.StartOfBlock)
    cur.insertText(prefix)
    cur.endEditBlock()
    editor.setTextCursor(cur)


def replace_block(editor, text: str, select_from: int = 0, select_len: int = 0):
    """整段插入（表格、代码块这类），插完把光标放到该填的位置。"""
    cur = editor.textCursor()
    cur.beginEditBlock()
    if cur.hasSelection():
        cur.removeSelectedText()
    cur.insertText(text)
    if select_len:
        pos = cur.position() - len(text) + select_from
        cur.setPosition(pos)
        cur.setPosition(pos + select_len, QTextCursor.KeepAnchor)
    cur.endEditBlock()
    editor.setTextCursor(cur)
    editor.setFocus()


def _heading(editor, level: int):
    if level == 0:
        cur = editor.textCursor()
        cur.beginEditBlock()
        cur.movePosition(QTextCursor.StartOfBlock)
        cur.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        line = cur.selectedText()
        cur.insertText(line.lstrip("#").lstrip())
        cur.endEditBlock()
        editor.setTextCursor(cur)
    else:
        line_prefix(editor, "#" * level + " ")


def _shift_heading(editor, delta: int):
    cur = editor.textCursor()
    cur.beginEditBlock()
    cur.movePosition(QTextCursor.StartOfBlock)
    cur.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
    line = cur.selectedText()
    n = len(line) - len(line.lstrip("#"))
    rest = line[n:].lstrip() if n else line
    n = max(0, min(6, n + delta))
    cur.insertText(("#" * n + " " + rest) if n else rest)
    cur.endEditBlock()
    editor.setTextCursor(cur)


def _indent(editor, outdent: bool):
    cur = editor.textCursor()
    cur.beginEditBlock()
    start = cur.selectionStart()
    end = cur.selectionEnd()
    cur.setPosition(start)
    cur.movePosition(QTextCursor.StartOfBlock)
    cur.setPosition(end, QTextCursor.KeepAnchor)
    text = cur.selectedText().replace("\u2029", "\n")
    lines = text.split("\n")
    if outdent:
        lines = [l[2:] if l.startswith("  ") else (l[1:] if l.startswith(" ") else l) for l in lines]
    else:
        lines = ["  " + l if l.strip() else l for l in lines]
    cur.insertText("\n".join(lines))
    cur.endEditBlock()
    editor.setTextCursor(cur)


def _copy_as_md(editor):
    cur = editor.textCursor()
    if cur.hasSelection():
        QGuiApplication.clipboard().setText(cur.selectedText().replace("\u2029", "\n"))


def _copy_as_html(editor):
    from ..md_render import convert
    cur = editor.textCursor()
    text = cur.selectedText().replace("\u2029", "\n") if cur.hasSelection() else editor.toPlainText()
    try:
        QGuiApplication.clipboard().setText(convert(text))
    except Exception:
        QGuiApplication.clipboard().setText(text)


def _paste_plain(editor):
    editor.insertPlainText(QGuiApplication.clipboard().text())


def _plain(editor) -> str:
    """去掉包裹符号的粗略实现（清除样式用）。"""
    import re
    cur = editor.textCursor()
    if not cur.hasSelection():
        return ""
    t = cur.selectedText().replace("\u2029", "\n")
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"~~(.+?)~~", r"\1", t)
    t = re.sub(r"`(.+?)`", r"\1", t)
    t = re.sub(r"</?u>", "", t)
    t = re.sub(r"<!--\s*(.*?)\s*-->", r"\1", t)
    return t


TABLE = """| 列1 | 列2 | 列3 |
| --- | --- | --- |
| a   | b   | c   |
| d   | e   | f   |
"""


def _insert_table(editor):
    cur = editor.textCursor()
    cur.beginEditBlock()
    cur.insertText("\n" + TABLE)
    cur.endEditBlock()
    editor.setTextCursor(cur)
    editor.setFocus()


# ── 菜单 ──
def _slim(menu: QMenu):
    """把菜单压紧凑。

    全局 QSS 里的 QMenu::item 在这套主题下压不下去（Fusion 度量 + 图标撑着），
    所以直接在菜单对象上设样式表 —— 对象级优先级最高，一定盖得住。
    """
    p = theme.c()
    menu.setStyleSheet(
        f"QMenu {{ background: {p['surface']}; border: 1px solid {p['line']};"
        f" border-radius: 6px; padding: 2px; font-size: 11px; }}"
        f"QMenu::item {{ padding: 0px 10px 0px 0px; margin: 0px;"
        f" min-height: 12px; border-radius: 4px; }}"
        f"QMenu::item:selected {{ background: {p['accent_soft']}; color: {p['ink']}; }}"
        f"QMenu::icon {{ padding-left: 2px; margin: 0px; }}"
        f"QMenu::separator {{ height: 1px; background: {p['line']}; margin: 2px 5px; }}"
        f"QMenu::right-arrow {{ width: 9px; height: 9px; margin-right: 1px; }}")


def build(editor, parent=None) -> QMenu:
    m = QMenu(parent or editor)

    # 格式
    f = m.addMenu(_i("wand-magic-sparkles"), "格式")
    f.addAction(_i("bold"), "加粗", lambda: wrap(editor, "**", "**"))
    f.addAction(_i("italic"), "斜体", lambda: wrap(editor, "*", "*"))
    f.addAction(_i("underline"), "下划线", lambda: wrap(editor, "<u>", "</u>"))
    f.addAction(_i("strikethrough"), "删除线", lambda: wrap(editor, "~~", "~~"))
    f.addAction(_i("code"), "行内代码", lambda: wrap(editor, "`", "`"))
    f.addAction(_i("comment"), "注释", lambda: wrap(editor, "<!-- ", " -->"))
    f.addSeparator()
    f.addAction(_i("link"), "超链接", lambda: wrap(editor, "[", "](https://)"))
    f.addAction(_i("image"), "图片", lambda: wrap(editor, "![", "](https://)"))
    f.addSeparator()
    f.addAction(_i("eraser"), "清除选中样式", lambda: replace_block(editor, _plain(editor)))

    # 段落
    p = m.addMenu(_i("paragraph"), "段落")
    names = {1: "一级标题", 2: "二级标题", 3: "三级标题",
             4: "四级标题", 5: "五级标题", 6: "六级标题"}
    for i in range(1, 7):
        p.addAction(_i("heading"), names[i], (lambda lv: (lambda: _heading(editor, lv)))(i))
    p.addAction(_i("paragraph"), "普通段落", lambda: _heading(editor, 0))
    p.addSeparator()
    p.addAction(_i("arrow-up-long"), "提升标题级别", lambda: _shift_heading(editor, -1))
    p.addAction(_i("arrow-down-long"), "降低标题级别", lambda: _shift_heading(editor, 1))
    p.addSeparator()
    p.addAction(_i("quote-left"), "引用", lambda: line_prefix(editor, "> "))

    # 列表
    lst = m.addMenu(_i("list"), "列表")
    lst.addAction(_i("list-ul"), "无序列表", lambda: line_prefix(editor, "- "))
    lst.addAction(_i("list-ol"), "有序列表", lambda: line_prefix(editor, "1. "))
    lst.addAction(_i("square-check"), "任务列表", lambda: line_prefix(editor, "- [ ] "))
    lst.addSeparator()
    lst.addAction(_i("indent"), "增加缩进", lambda: _indent(editor, False))
    lst.addAction(_i("outdent"), "减少缩进", lambda: _indent(editor, True))

    # 插入
    ins = m.addMenu(_i("circle-plus"), "插入")
    ins.addAction(_i("table"), "表格", lambda: _insert_table(editor))
    ins.addAction(_i("file-code"), "代码块", lambda: replace_block(editor, "```python\n\n```", 11, 0))
    ins.addAction(_i("square-root-variable"), "公式块", lambda: replace_block(editor, "$$\n\n$$", 3, 0))
    ins.addAction(_i("minus"), "水平分割线", lambda: replace_block(editor, "\n\n---\n\n"))
    ins.addAction(_i("bars-staggered"), "内容目录", lambda: replace_block(editor, "\n[TOC]\n"))
    ins.addSeparator()
    ins.addAction(_i("link"), "链接引用", lambda: replace_block(editor, "[标题][ref]\n\n[ref]: https://", 17, 0))
    ins.addAction(_i("asterisk"), "脚注", lambda: replace_block(editor, "[^1]\n\n[^1]: ", 4, 0))
    ins.addAction(_i("caret-down"), "折叠面板", lambda: replace_block(
        editor, "<details>\n<summary>点开看</summary>\n\n内容\n\n</details>", 26, 2))

    # 复制 / 粘贴：直接平铺在一级，不做子菜单
    m.addSeparator()
    m.addAction(_i("copy"), "复制为 Markdown", lambda: _copy_as_md(editor))
    m.addAction(_i("code"), "复制为 HTML 代码", lambda: _copy_as_html(editor))
    m.addAction(_i("paste"), "粘贴为纯文本", lambda: _paste_plain(editor))

    # 子菜单也要单独压（对象级样式不会从父菜单继承）
    _slim(m)
    for act in m.actions():
        sub = act.menu()
        if sub is not None:
            _slim(sub)

    return m
