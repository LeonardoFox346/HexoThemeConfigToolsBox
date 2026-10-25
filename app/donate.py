"""捐赠码：优先用内置图（防替换），没有再用程序目录里的图片。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPixmap

from . import donate_qr

ROOT = Path(__file__).resolve().parent.parent

CANDIDATES = [
    ("微信", ROOT / "donate-wechat.png"),
    ("支付宝", ROOT / "donate-alipay.png"),
    ("赞赏码", ROOT / "donate.png"),
]

_cache: QPixmap | None = None


def embedded_ok() -> bool:
    try:
        return donate_qr.verify()
    except Exception:
        return False


def pixmap() -> QPixmap | None:
    """内置赞赏码。校验不过就返回 None（说明被改过）。"""
    global _cache
    if _cache is not None:
        return _cache
    if not embedded_ok():
        return None
    pm = QPixmap()
    if pm.loadFromData(donate_qr.image_bytes(), "PNG"):
        _cache = pm
        return pm
    return None


def images() -> list[tuple[str, Path]]:
    return [(name, p) for name, p in CANDIDATES if p.exists()]


def has_any() -> bool:
    return pixmap() is not None or bool(images())
