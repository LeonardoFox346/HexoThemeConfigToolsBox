# -*- mode: python ; coding: utf-8 -*-
"""完整版：不排除任何 Qt 组件（含 QtWebEngine，样式预览可用）。"""
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "fonts"), "fonts"),
    (str(ROOT / "app" / "assets"), "app/assets"),
    (str(ROOT / "app.ico"), "."),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "EULA.txt"), "."),
    (str(ROOT / "THIRD-PARTY-NOTICES.md"), "."),
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    excludes=["tkinter", "unittest", "pydoc_data"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NardoFoxWriteDesk-Full",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="NardoFoxWriteDesk-Full",
)
