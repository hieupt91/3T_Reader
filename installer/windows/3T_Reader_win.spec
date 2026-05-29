# -*- mode: python ; coding: utf-8 -*-
# Windows build spec for 3T Reader
# Build with: pyinstaller installer\windows\3T_Reader_win.spec

import sys
import os
from pathlib import Path

assert sys.platform == "win32", "This spec is Windows-only"

# SPECPATH = directory of this spec file (installer\windows\)
# ROOT     = repo root (two levels up)
ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

datas = [
    (os.path.join(ROOT, "assets"),              "assets"),
    (os.path.join(ROOT, "third_party", "pdfjs"), "third_party/pdfjs"),
]

hiddenimports = [
    "pypdfium2",
    "pikepdf",
    "reportlab",
    "PySide6.QtPrintSupport",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebChannel",
    "packages.signing.windows_provider",
]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyMuPDF", "fitz", "PyKCS11"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="3T Reader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(ROOT, "assets", "icon.ico") if os.path.exists(os.path.join(ROOT, "assets", "icon.ico")) else None,
    version=os.path.join(SPECPATH, "version_info.txt") if os.path.exists(os.path.join(SPECPATH, "version_info.txt")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="3T Reader",
)
