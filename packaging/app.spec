# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 配置：精简版 onedir 打包。

排除 QtWebEngine / Quick / Qml / Pdf 等用不到的模块，体积能小一大截。
代价：写文章页的「样式预览」按钮不可用（程序会自动禁用并提示）。
"""
import fnmatch
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

EXCLUDES = [
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtDesigner", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtBluetooth",
    "PySide6.QtPositioning", "PySide6.QtNfc", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech",
    "PySide6.QtHelp", "PySide6.QtUiTools", "PySide6.QtNetworkAuth",
    "tkinter", "unittest", "pydoc_data",
]

BIN_PATTERNS = [
    "Qt6WebEngine*", "Qt6WebChannel*", "Qt6Pdf*", "Qt6Qml*", "Qt6Quick*",
    "Qt6Designer*", "Qt6Sql*", "Qt6Test*", "Qt6Multimedia*", "Qt6Charts*",
    "Qt6DataVisualization*", "Qt6Sensors*", "Qt6SerialPort*", "Qt6Bluetooth*",
    "Qt6Positioning*", "Qt6Nfc*", "Qt6RemoteObjects*", "Qt6Scxml*",
    "Qt6StateMachine*", "Qt6TextToSpeech*", "Qt6Help*", "Qt6NetworkAuth*",
    "qtwebengine_*",
]

DATA_SKIP = ("PySide6/translations/qtwebengine_locales", "PySide6/resources",
             "PySide6/translations/qtwebengine")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    excludes=EXCLUDES,
    noarchive=False,
)

a.binaries = [b for b in a.binaries
              if not any(fnmatch.fnmatch(Path(b[0]).name, p) for p in BIN_PATTERNS)]
a.datas = [d for d in a.datas
           if not any(str(d[0]).replace("\\", "/").startswith(s) for s in DATA_SKIP)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NardoFoxWriteDesk",
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
    name="NardoFoxWriteDesk",
)
