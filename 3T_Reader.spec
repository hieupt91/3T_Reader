# -*- mode: python ; coding: utf-8 -*-
# macOS build spec for 3T Reader

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
    # Export (pdf2docx removed due to GPL-3.0)
    'pdfplumber', 'openpyxl', 'openpyxl.styles',
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
    'packages.platform.macos',
    'packages.signing.macos_provider',
    'packages.license_client.keychain',
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
    excludes=['PyMuPDF', 'fitz', 'PyKCS11', 'tkinter', 'matplotlib', 'pdf2docx'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='3T Reader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True, # Recommended for macOS
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.icns' if os.path.exists('assets/icon.icns') else 'assets/app.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='3T Reader',
)

app = BUNDLE(
    coll,
    name='3T Reader.app',
    icon='assets/icon.icns' if os.path.exists('assets/icon.icns') else 'assets/app.ico',
    bundle_identifier='vn.3tcompany.reader',
    info_plist={
        'CFBundleName': '3T Reader',
        'CFBundleDisplayName': '3T Reader',
        'CFBundleExecutable': '3T Reader',
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': '0.8.0',
        'NSHighResolutionCapable': 'True',
    },
)
