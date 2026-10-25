"""带行号栏和当前行高亮的 Markdown 编辑器。

行号用 Qt 官方的 LineNumberArea 做法：跟正文同一个滚动条、同一套字体度量，
所以永远对齐。自动换行保持开启（中文写作需要），行号只画在每个逻辑行的首行位置。
"""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from .. import theme


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_line_numbers(event)


class MdEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._area = LineNumberArea(self)

        self.blockCountChanged.connect(self._update_width)
        self.updateRequest.connect(self._update_area)
        self.cursorPositionChanged.connect(self._highlight_current)
        self.selectionChanged.connect(self._highlight_current)

        self._update_width(0)
        self._highlight_current()

    # ── 行号栏尺寸 ──
    def line_number_width(self) -> int:
        digits = 1
        n = max(1, self.blockCount())
        while n >= 10:
            n //= 10
            digits += 1
        return 16 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_width(self, _=0):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_area(self, rect, dy):
        if dy:
            self._area.scroll(0, dy)
        else:
            self._area.update(0, rect.y(), self._area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._area.setGeometry(QRect(cr.left(), cr.top(),
                                     self.line_number_width(), cr.height()))

    # ── 画行号 ──
    def paint_line_numbers(self, event):
        p = theme.c()
        painter = QPainter(self._area)
        painter.fillRect(event.rect(), QColor(p["panel"]))

        block = self.firstVisibleBlock()
        num = block.blockNumber()
        offset = self.contentOffset()
        top = self.blockBoundingGeometry(block).translated(offset).top()
        bottom = top + self.blockBoundingRect(block).height()
        cur = self.textCursor().blockNumber()
        h = self.fontMetrics().height()
        w = self._area.width() - 6

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                is_cur = (num == cur)
                painter.setPen(QColor(p["accent"] if is_cur else p["ink2"]))
                painter.drawText(0, int(top), w, h, Qt.AlignRight, str(num + 1))
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            num += 1

    # ── 当前行高亮 ──
    def _highlight_current(self):
        if self.isReadOnly():
            self.setExtraSelections([])
            return
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(theme.c()["chip"]))
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel])
        if not self._area.isHidden():
            self._area.update()

    def apply_theme(self):
        self._highlight_current()
        self._area.update()
