from pathlib import Path
root=Path(SPECPATH)
# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    [str(root/'run_connect.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root/'computer_connect/assets'), 'computer_connect/assets')],
    hiddenimports=[],
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
    name='CouchsideComputerConnect',
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
    icon=[str(root/'computer_connect/assets/icon.png')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CouchsideComputerConnect',
)
app = BUNDLE(
    coll,
    name='CouchsideComputerConnect.app',
    icon=str(root/'computer_connect/assets/icon.png'),
    bundle_identifier='com.couchside.computerconnect.preview',
    info_plist={'NSLocalNetworkUsageDescription': 'Find Couchside PCs on your local network when you choose Scan for boxes.'},
)
