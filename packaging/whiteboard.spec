# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（本地自用，不做签名与升级回滚）。

用法（仓库根目录）：
    .venv\\Scripts\\pyinstaller.exe packaging\\whiteboard.spec --noconfirm

产物：packaging\\dist\\CameraWhiteboard\\CameraWhiteboard.exe
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).resolve().parent          # 仓库根
PACKAGING = ROOT / "packaging"

# 砍掉用不到的 Qt 子模块与科学计算库，控制体积
EXCLUDES = [
    "tkinter",
    "pydoc_data",
    "xmlrpc",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQml",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtBluetooth",
    "PySide6.QtSerialPort",
    "PySide6.QtPositioning",
    "PySide6.QtSensors",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtHelp",
    "PySide6.QtUiTools",
    "matplotlib",
    "pandas",
    "scipy",
    "PIL",
    "pytest",
]

a = Analysis(
    [str(PACKAGING / "entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=collect_data_files("imageio_ffmpeg") + [(str(ROOT / "config/app.json"), "config")],  # 自带 ffmpeg.exe，720p 采集要用
    hiddenimports=["ui.camera_whiteboard.app"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

# Qt uses Windows' built-in ICU API. An unrelated ICU DLL on the build machine's
# PATH (e.g. Poppler) has the same name but incompatible exports. Do not shadow
# the Windows system component in the bundle.
a.binaries = [item for item in a.binaries if Path(item[0]).name.lower() != "icuuc.dll"]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CameraWhiteboard",
    debug=False,
    strip=False,
    upx=False,
    console=False,         # 不弹控制台；日志写到 .run/app.log
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CameraWhiteboard",
)
