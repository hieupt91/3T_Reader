# -*- mode: python ; coding: utf-8 -*-
# Windows build spec for 3T Reader
# Build: pyinstaller 3T_Reader.spec --distpath dist\win --workpath build\win --noconfirm

import sys
import os

datas = []
binaries = []

hiddenimports = [
    # PDF engine
    'pypdfium2', 'pikepdf', 'pikepdf._core',
    # Qt
    'PySide6.QtPrintSupport', 'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineCore', 'PySide6.QtWebChannel',
    # Export
    'pdf2docx', 'pdfplumber', 'openpyxl', 'openpyxl.styles',
    'reportlab', 'reportlab.lib', 'reportlab.platypus',
    # Signing
    'pyhanko', 'pkcs11', 'cryptography',
    # OCR
    'pytesseract', 'PIL', 'PIL.Image',
    # AI
    'anthropic', 'openai', 'numpy', 'numpy.core',
    # Requests / network
    'requests', 'urllib3', 'certifi',
    # Internal packages
    'packages.platform.windows',
    'packages.signing.windows_provider',
    'packages.license_client.credential_manager',
    'packages.ai.provider',
    'packages.ai.translate',
    'packages.ai.summarize',
    'packages.ai.chat_pdf',
    'packages.ai.semantic_search',
    'packages.update_client.checker',
    'packages.ocr.engine',
    'packages.audit.logger',
]

datas += [('assets', 'assets')]
datas += [('third_party/pdfjs', 'third_party/pdfjs')]
datas += [('EULA.md', '.')]
datas += [('LICENSES.md', '.')]
datas += [('THIRD_PARTY_NOTICES.md', '.')]
datas += [('PRIVACY_POLICY.md', '.')]


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyMuPDF', 'fitz', 'PyKCS11', 'tkinter', 'matplotlib'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='3T_Reader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\icon.ico',
    version_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='3T_Reader',
)
