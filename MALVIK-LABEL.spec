# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

a = Analysis(
    ['run_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('alembic_config', 'alembic_config'),
        ('alembic.ini', '.'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'engineio.async_drivers.asgi',
        'aiosmtplib',
        'openpyxl',
        'sqlalchemy.ext.baked',
        'sqlalchemy.dialects.sqlite',
        'alembic',
        'app.routers.routers',
        'app.routers.settings_router',
        'app.routers.today_router',
        'app.models.models',
        'app.services.excel_import',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
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
    name='MALVIK-LABEL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
