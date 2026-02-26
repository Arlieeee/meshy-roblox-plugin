# -*- mode: python ; coding: utf-8 -*-
import sys

a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
        icon='icon.ico',
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
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='MeshyRobloxBridge',
        icon='icon.icns',          # convert icon.ico → icon.icns on mac
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

    app = BUNDLE(
        exe,
        name='MeshyRobloxBridge.app',
        icon='icon.icns',
        bundle_identifier='ai.meshy.roblox-bridge',
        info_plist={
            'CFBundleDisplayName': 'Meshy Roblox Bridge',
            'CFBundleShortVersionString': '0.1.0',
            'CFBundleVersion': '0.1.0',
            'NSHighResolutionCapable': True,
        },
    )
