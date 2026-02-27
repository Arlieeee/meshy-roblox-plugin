# -*- mode: python ; coding: utf-8 -*-
import os
import sys

root = os.path.abspath(os.path.join(SPECPATH, '..'))

# Platform-specific icon data
if sys.platform == 'win32':
    icon_datas = [(os.path.join(root, 'assets/icon.ico'), '.')]
else:
    icon_datas = [(os.path.join(root, 'assets/icon.icns'), '.')]

a = Analysis(
    [os.path.join(root, 'server.py')],
    pathex=[root],
    binaries=[],
    datas=icon_datas,
    hiddenimports=[
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
        'click',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL.ImageQt',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
        'test',
        'unittest',
        'email',
        'html',
        'http.server',
        'xmlrpc',
        'pydoc',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# ── Windows ────────────────────────────────────────────────────
if sys.platform == 'win32':
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='MeshyRobloxBridge',
        icon=os.path.join(root, 'assets/icon.ico'),
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

# ── macOS ──────────────────────────────────────────────────────
# Use onedir mode (exclude_binaries=True + COLLECT) so that Tcl/Tk
# libraries are placed inside the .app bundle properly. Onefile mode
# combined with an .app bundle is broken on macOS and causes a blank window.
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,     # onedir: binaries go into COLLECT, not the exe
        name='MeshyRobloxBridge',
        icon=os.path.join(root, 'assets/icon.icns'),
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,                 # UPX not supported on macOS
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=True,       # macOS open-file event support
        target_arch=None,          # None = native; 'universal2' for fat binary
        codesign_identity=None,
        entitlements_file=None,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name='MeshyRobloxBridge',
    )

    app = BUNDLE(
        coll,
        name='MeshyRobloxBridge.app',
        icon=os.path.join(root, 'assets/icon.icns'),
        bundle_identifier='ai.meshy.roblox-bridge',
        info_plist={
            'CFBundleDisplayName': 'Meshy Roblox Bridge',
            'CFBundleShortVersionString': '0.1.0',
            'CFBundleVersion': '0.1.0',
            'NSHighResolutionCapable': True,
        },
    )
