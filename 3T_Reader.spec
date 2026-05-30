# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os

datas = []
binaries = []
hiddenimports = ['pypdfium2', 'pikepdf', 'PySide6.QtPrintSupport', 'PySide6.QtWebEngineWidgets']
datas += [('assets', 'assets')]
datas += [('third_party/pdfjs', 'third_party/pdfjs')]
if os.path.isdir('app/locales'):
    datas += [('app/locales', 'app/locales')]
if os.path.isdir(r'C:\Program Files\Tesseract-OCR'):
    datas += [(r'C:\Program Files\Tesseract-OCR', 'Tesseract-OCR')]
elif os.path.isdir('third_party/tesseract'):
    datas += [('third_party/tesseract', 'Tesseract-OCR')]


def _merge_collected(package_name):
    collected_datas, collected_binaries, collected_hiddenimports = collect_all(package_name)
    datas.extend(collected_datas)
    binaries.extend(collected_binaries)
    hiddenimports.extend(collected_hiddenimports)


# Native PDF backends can require package-provided binaries/data at runtime.
for _package in ('pypdfium2', 'pikepdf'):
    _merge_collected(_package)


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    icon='assets/app.ico',
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
