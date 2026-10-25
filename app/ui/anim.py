"""界面动效：按钮水波纹、页面淡入、错误抖动、加载转圈。

全部基于 Qt 自带的 QPropertyAnimation / QPainter，不引第三方动画库 ——
这类库往往自带一整套控件替换，会把 qt-material 的 MD2 样式顶掉。

几处刻意的取舍：
  · 水波纹用「透明覆盖层」而不是子类化按钮，这样不会破坏 QSS 画的按钮外观；
  · 淡入跳过得很快的页面，并且动画结束立刻摘掉 QGraphicsOpacityEffect ——
    这个 effect 会让 QWebEngineView 渲染异常（黑屏），所以含浏览器的页面直接不做；
  · 抖动用改 pos 的方式，只适合顶层窗口（对话框），布局里的控件会被重新摆回去。
"""
from __future__ import annotations

from PySide6.QtCore import (
    QAbstractAnimation, QEasingCurve, QEvent, QPoint, QPointF,
    QPropertyAnimation, QRectF, Qt, QTimer, QVariantAnimation,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QPushButton, QWidget

from .. import theme


# ══════════════ 按钮水波纹 ══════════════
class _RippleLayer(QWidget):
    """盖在按钮上的一层透明画布，只负责画扩散的圆。"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._progress = 1.0
        self._origin = QPointF(0, 0)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(420)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_tick)

    def _on_tick(self, v):
        self._progress = float(v)
        self.update()

    def trigger(self, pos: QPoint):
        self._origin = QPointF(pos)
        self.resize(self.parentWidget().size())
        self.raise_()
        self._progress = 0.0
        self.update()
        self._anim.stop()
        self._anim.start()

    def eventFilter(self, obj, event):
        """跟着父控件改尺寸。用事件过滤器而不是替换 resizeEvent ——
        Qt 走 C++ 虚表，Python 里给实例赋 resizeEvent 是不会被调到的。"""
        if event.type() == QEvent.Resize:
            self.resize(obj.size())
        return False

    def paintEvent(self, event):
        if self._progress >= 1.0:
            return
        p = theme.c()
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        max_r = max(self.width(), self.height()) * 1.2
        r = max(2.0, max_r * self._progress)
        # 深色主题下按钮多是深底，用白波纹才看得出；
        # 浅色主题下按钮是白底，改用强调色。
        col = QColor(255, 255, 255) if theme.is_dark() else QColor(p["accent"])
        col.setAlpha(int(175 * (1.0 - self._progress)))
        g.setPen(Qt.NoPen)
        g.setBrush(col)
        g.drawEllipse(self._origin, r, r)


def install_ripple(button: QWidget):
    """给按钮接上点击水波纹。重复调用无副作用。"""
    if not isinstance(button, QWidget) or getattr(button, "_ripple", None) is not None:
        return

    layer = _RippleLayer(button)
    layer.resize(button.size())
    layer.show()
    button._ripple = layer
    button.installEventFilter(layer)      # 尺寸变化时让覆盖层跟着走

    def on_press():
        # 从按钮中心扩散
        layer.trigger(QPoint(button.width() // 2, button.height() // 2))

    button.pressed.connect(on_press)


def install_ripple_tree(root: QWidget):
    """把整棵界面里的按钮都接上水波纹。"""
    for b in root.findChildren(QPushButton):
        install_ripple(b)


# ══════════════ 页面淡入 ══════════════
def fade_in(widget: QWidget, ms: int = 180):
    """页面淡入。

    页面里若有 QWebEngineView，先把它藏起来再淡入、结束再显出来 ——
    浏览器不吃 QGraphicsOpacityEffect（会黑屏或闪白），但它藏起来的时候
    其它部分照样能正常淡入。之前图省事整页跳过，结果写文章页只要开过一次
    样式预览就再也没动画了。
    """
    if widget is None:
        return

    # 上一轮淡入没摘干净的 effect 先清掉，否则透明度可能停在 0（整页发黑）
    if widget.graphicsEffect() is not None:
        widget.setGraphicsEffect(None)

    # 窗口还没显示时不做淡入：这时候动画经常起不来，
    # effect 留在 0 上，页面就是一片空白
    if not widget.isVisible():
        return

    webs = []
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView
        webs = widget.findChildren(QWebEngineView)
    except Exception:
        webs = []
    for wv in webs:
        try:
            wv.setVisible(False)
        except RuntimeError:
            pass

    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)

    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)

    def done():
        try:
            widget.setGraphicsEffect(None)   # 必须摘掉，否则影响子控件绘制
        except RuntimeError:
            pass
        for wv in webs:
            try:
                wv.setVisible(True)
            except RuntimeError:
                pass

    anim.finished.connect(done)
    widget._fade_anim = anim
    anim.start(QAbstractAnimation.DeleteWhenStopped)


# ══════════════ 错误抖动 ══════════════
def shake(widget: QWidget, ms: int = 360, amp: int = 9):
    """左右抖一下。只对顶层窗口（对话框）有效 —— 布局里的控件会被重新摆回去。"""
    if widget is None:
        return
    base = widget.pos()
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(ms)
    for t, dx in ((0.0, 0), (0.12, -amp), (0.28, amp), (0.44, -int(amp * 0.6)),
                  (0.60, int(amp * 0.6)), (0.76, -int(amp * 0.3)), (1.0, 0)):
        anim.setKeyValueAt(t, base + QPoint(dx, 0))
    anim.setEasingCurve(QEasingCurve.OutQuad)
    widget._shake_anim = anim
    anim.start(QAbstractAnimation.DeleteWhenStopped)


# ══════════════ 加载转圈 ══════════════
class Spinner(QWidget):
    """一个细圆弧转圈。start() / stop() 控制。"""

    def __init__(self, parent=None, size: int = 18):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self):
        self.show()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 9) % 360
        self.update()

    def paintEvent(self, event):
        p = theme.c()
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        g.translate(self.width() / 2.0, self.height() / 2.0)
        g.rotate(self._angle)

        pen = QPen(QColor(p["accent"]), 2.4)
        pen.setCapStyle(Qt.RoundCap)
        g.setPen(pen)
        r = (min(self.width(), self.height()) - 6) / 2.0
        g.drawArc(QRectF(-r, -r, 2 * r, 2 * r), 0, 110 * 16)


# ══════════════ 颜色脉冲（错误高亮）══════════════
def flash_error(widget: QWidget, ms: int = 720):
    """把输入框的边框闪成错误色再恢复。用于「这里没填」的提示。"""
    if widget is None:
        return
    p = theme.c()
    ok_style = widget.styleSheet()
    bad = f"border: 1px solid {p['bad']}; border-radius: 6px;"
    widget.setStyleSheet(bad)
    QTimer.singleShot(ms, lambda: _restore(widget, ok_style))


def _restore(widget, style):
    try:
        widget.setStyleSheet(style)
    except RuntimeError:
        pass
