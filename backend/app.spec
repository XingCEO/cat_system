# -*- mode: python ; coding: utf-8 -*-
"""
貓星人賺大錢 - PyInstaller 打包配置
在 Windows 上執行: pyinstaller app.spec
"""

import os
import sys

block_cipher = None

# 取得目前目錄
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['launcher.py'],
    pathex=[SPEC_DIR],
    binaries=[],
    datas=[
        # 打包靜態前端檔案
        ('static', 'static'),
        # 打包 Python 模組
        ('main.py', '.'),
        ('config.py', '.'),
        ('database.py', '.'),
        ('routers', 'routers'),
        ('services', 'services'),
        ('models', 'models'),
        ('schemas', 'schemas'),
        ('utils', 'utils'),
    ],
    hiddenimports=[
        # FastAPI 相關
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'pydantic',
        'pydantic_settings',
        # 資料庫
        'sqlalchemy',
        'sqlalchemy.ext.asyncio',
        'aiosqlite',
        'greenlet',
        # 資料處理
        'pandas',
        'numpy',
        'openpyxl',
        'xlsxwriter',
        # HTTP
        'httpx',
        'aiohttp',
        # 其他
        'cachetools',
        'dateutil',
        'dotenv',
        'multipart',
        # 編碼
        'encodings',
        'encodings.idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PIL',
        'scipy',
        'pytest',
    ],
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
    name='貓星人賺大錢',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 顯示命令列視窗（方便看 log）
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以加入 icon='app.ico'
)
