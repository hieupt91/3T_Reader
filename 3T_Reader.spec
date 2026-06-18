# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os

datas = []
binaries = []
hiddenimports = ['pypdfium2', 'pikepdf', 'pyhanko.network', 'pyhanko.network.requests', 'pyhanko_certvalidator', 'pyhanko_certvalidator.fetchers.requests_fetchers', 'PySide6.QtPrintSupport', 'PySide6.QtWebEngineWidgets', 'pdf2docx', 'pdfplumber', 'openpyxl', 'openai', 'anthropic', 'huggingface_hub', 'google.genai', 'requests', 'keyring']
datas += [('assets', 'assets')]
datas += [('styles', 'styles')]
datas += [('third_party/pdfjs', 'third_party/pdfjs')]
if os.path.isdir('app/locales'):
    datas += [('app/locales', 'app/locales')]
if os.path.isdir('third_party/tesseract'):
    datas += [('third_party/tesseract', 'Tesseract-OCR')]
elif os.path.isdir(r'C:\Program Files\Tesseract-OCR'):
    datas += [(r'C:\Program Files\Tesseract-OCR', 'Tesseract-OCR')]

import sys
if sys.platform == 'darwin':
    if os.path.isdir('venv_piper'):
        datas += [('venv_piper', 'venv_piper')]
else:
    if os.path.isdir('piper_bin'):
        datas += [('piper_bin', 'piper_bin')]



def _merge_collected(package_name):
    collected_datas, collected_binaries, collected_hiddenimports = collect_all(package_name)
    datas.extend(collected_datas)
    binaries.extend(collected_binaries)
    hiddenimports.extend(collected_hiddenimports)

from PyInstaller.utils.hooks import collect_submodules
hiddenimports.extend(collect_submodules('app'))
hiddenimports.extend(collect_submodules('packages'))
hiddenimports.extend(collect_submodules('styles'))
hiddenimports.extend(collect_submodules('core'))


# Native PDF backends can require package-provided binaries/data at runtime.
for _package in ('pypdfium2', 'pikepdf', 'pyhanko', 'pyhanko_certvalidator'):
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

import sys
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='3T Reader.app',
        icon='assets/app.icns' if os.path.exists('assets/app.icns') else None,
        bundle_identifier='com.3t.reader',
        info_plist={
            'CFBundleShortVersionString': '1.0.19',
            'CFBundleVersion': '1.0.19',
            'NSHighResolutionCapable': True,
            'NSMicrophoneUsageDescription': 'Used for audio recording',
            'CFBundleDocumentTypes': [
                {
                    'CFBundleTypeName': 'PDF Document',
                    'CFBundleTypeRole': 'Editor',
                    'LSHandlerRank': 'Owner',
                    'LSItemContentTypes': ['com.adobe.pdf']
                }
            ]
        }
    )
