"""Markdown 语法高亮。只做「看得清」的程度，不做完整解析。"""
from __future__ import annotations

import re

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

from .. import theme


def _fmt(color: str, bold=False, italic=False, mono=False, underline=False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    if italic:
        f.setFontItalic(True)
    if underline:
        f.setFontUnderline(True)
    if mono:
        f.setFontFamilies(["JetBrains Mono", "Consolas", "Cascadia Mono"])
    return f


class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rebuild()

    def rebuild(self):
        p = theme.c()
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        def add(pattern: str, fmt: QTextCharFormat):
            self.rules.append((QRegularExpression(pattern), fmt))

        # Front Matter 区间
        self.fm_fmt = _fmt(p["good"])
        self.fm_key = _fmt(p["accent"])
        self.fm_val = _fmt(p["ink2"])

        add(r"^#{1,6}\s.*$", _fmt(p["accent"], bold=True))
        add(r"\*\*[^*\n]+\*\*", _fmt(p["ink"], bold=True))
        add(r"(?<!\*)\*[^*\n]+\*(?!\*)", _fmt(p["ink"], italic=True))
        add(r"`[^`\n]+`", _fmt(p["warn"], mono=True))
        add(r"^\s*```.*$", _fmt(p["warn"], mono=True))
        add(r"!\[[^\]\n]*\]\([^)\n]*\)", _fmt(p["good"]))
        add(r"\[[^\]\n]*\]\([^)\n]*\)", _fmt(p["accent"], underline=True))
        add(r"^\s*[-*+]\s", _fmt(p["accent"]))
        add(r"^\s*\d+\.\s", _fmt(p["accent"]))
        add(r"^\s*>\s.*$", _fmt(p["ink2"], italic=True))
        add(r"^\s*---+\s*$", _fmt(p["line"]))
        add(r"^\s*\|.*\|\s*$", _fmt(p["ink2"], mono=True))
        add(r"{%[^%]*%}", _fmt(p["bad"]))
        add(r"<!--.*?-->", _fmt(p["ink2"], italic=True))
        self._in_code = False

    def highlightBlock(self, text: str):
        p = theme.c()
        # Front Matter：文件开头到第二个 ---
        if self.currentBlock().blockNumber() < 40:
            st = self.previousBlockState()
            if self.currentBlock().blockNumber() == 0 and text.strip() == "---":
                self.setCurrentBlockState(1)
                self.setFormat(0, len(text), self.fm_fmt)
                return
            if st == 1:
                if text.strip() == "---":
                    self.setCurrentBlockState(2)
                    self.setFormat(0, len(text), self.fm_fmt)
                else:
                    self.setCurrentBlockState(1)
                    i = text.find(":")
                    if 0 < i < len(text):
                        self.setFormat(0, i, self.fm_key)
                        self.setFormat(i + 1, len(text) - i - 1, self.fm_val)
                    else:
                        self.setFormat(0, len(text), self.fm_val)
                return

        # 代码块
        if text.strip().startswith("```"):
            self.setCurrentBlockState(0 if self.previousBlockState() == 3 else 3)
            self.setFormat(0, len(text), _fmt(p["warn"]))
            return
        if self.previousBlockState() == 3:
            self.setCurrentBlockState(3)
            self.setFormat(0, len(text), _fmt(p["warn"]))
            return

        for rx, fmt in self.rules:
            m = rx.globalMatch(text)
            while m.hasNext():
                hit = m.next()
                self.setFormat(hit.capturedStart(), hit.capturedLength(), fmt)
