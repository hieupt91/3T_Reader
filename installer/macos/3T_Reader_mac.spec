# -*- mode: python ; coding: utf-8 -*-
# macOS .app bundle spec for 3T Reader
# Build with: pyinstaller installer/macos/3T_Reader_mac.spec

import sys
from pathlib import Path

assert sys.platform == "darwin", "This spec is macOS-only"

datas = [
    ("assets", "assets"),
    ("third_party/pdfjs", "third_party/pdfjs"),
]

hiddenimports = [
    "pypdfium2",
    "pikepdf",
    "reportlab",
    "PySide6.QtPrintSupport",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebChannel",
    "packages.platform.macos",
    "packages.signing.macos_provider",
]

a = Analysis(
    ["main.py"],
    pathex=[],
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
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file="installer/macos/entitlements.plist",
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

app = BUNDLE(
    coll,
    name="3T Reader.app",
    icon=None,
    bundle_identifier="com.3t.reader",
    version="1.0.2",
    info_plist={
        "CFBundleName": "3T Reader",
        "CFBundleDisplayName": "3T Reader",
        "CFBundleIdentifier": "com.3t.reader",
        "CFBundleVersion": "1.0.2",
        "CFBundleShortVersionString": "1.0.2",
        "CFBundleExecutable": "3T Reader",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright 2026 3T Company. All rights reserved.",
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "PDF Document",
                "CFBundleTypeExtensions": ["pdf"],
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Default",
            }
        ],
        "LSMinimumSystemVersion": "12.0",
    },
)
