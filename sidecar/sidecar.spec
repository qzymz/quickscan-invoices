# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['sidecar_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../templates', 'templates'),
        ('../static', 'static'),
    ],
    hiddenimports=[
        'main',
        'ocr_engine',
        'field_extractor',
        'export',
        'invoice_config',
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        'rapidocr',
        'fitz',
        'PIL',
        'numpy',
        'pandas',
        'openpyxl',
        'fastapi',
        'jinja2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='quickscan-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='quickscan-sidecar',
)
