# -*- mode: python ; coding: utf-8 -*-
# macOS .app bundle spec for 3T Reader
# Build with: pyinstaller installer/macos/3T_Reader_mac.spec

import sys
import os
from pathlib import Path

assert sys.platform == "darwin", "This spec is macOS-only"

# SPECPATH = directory of this spec file (installer/macos/)
# ROOT     = repo root (two levels up)
ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

datas = [
    (os.path.join(ROOT, "assets"),              "assets"),
    (os.path.join(ROOT, "third_party", "pdfjs"), "third_party/pdfjs"),
    (os.path.join(ROOT, "EULA.md"),             "."),
    (os.path.join(ROOT, "LICENSES.md"),         "."),
    (os.path.join(ROOT, "THIRD_PARTY_NOTICES.md"), "."),
    (os.path.join(ROOT, "PRIVACY_POLICY.md"),   "."),
]

hiddenimports = [
    # PDF engine
    "pypdfium2", "pikepdf", "pikepdf._core",
    # Qt
    "PySide6.QtPrintSupport", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore", "PySide6.QtWebChannel",
    # Export
    "pdf2docx", "pdfplumber", "openpyxl", "openpyxl.styles",
    "reportlab", "reportlab.lib", "reportlab.platypus",
    # Signing
    "pyhanko", "pkcs11", "cryptography",
    # OCR
    "pytesseract", "PIL", "PIL.Image",
    # AI
    "anthropic", "openai", "numpy", "numpy.core",
    # Requests / network
    "requests", "urllib3", "certifi",
    # Internal packages
    "packages.platform.macos",
    "packages.signing.macos_provider",
    "packages.license_client.credential_manager",
    "packages.ai.provider",
    "packages.ai.translate",
    "packages.ai.summarize",
    "packages.ai.chat_pdf",
    "packages.ai.semantic_search",
    "packages.update_client.checker",
    "packages.ocr.engine",
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
    excludes=["PyMuPDF", "fitz", "PyKCS11", "tkinter", "matplotlib"],
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
    entitlements_file=os.path.join(SPECPATH, "entitlements.plist"),
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
    icon=os.path.join(ROOT, "assets", "3TReader.icns"),
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
