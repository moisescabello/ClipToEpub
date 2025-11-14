# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

project_root = os.path.abspath('.')

a = Analysis(
    ['src/cliptoepub/tray_app_windows.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        ('templates/*', 'templates'),
        ('resources/*', 'resources'),
    ],
    hiddenimports=[
        'cliptoepub.content_processor',
        'bs4',
        'newspaper',
        'lxml_html_clean',
        'PIL._imaging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'pandas', 'pytest', 'ipython'],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ClipToEpubTray',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # avoid packers to reduce AV false positives
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='ClipToEpubTray'
)
