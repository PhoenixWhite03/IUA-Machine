# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # Incluimos toda tu carpeta de recursos
    datas=[('src/assets', 'src/assets')],
    # Forzamos la inclusión de las librerías de datos y soporte SVG
    hiddenimports=['pandas', 'openpyxl', 'pyarrow', 'pyarrow.parquet', 'PyQt5.QtSvg'],
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
    name='IUA Machine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # Oculta la terminal negra
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['src/assets/IUA-Machine-LOGO-remove-bg-io.ico'], # Tu icono oficial
    version='version-info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='IUA Machine',
)
