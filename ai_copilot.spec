# PyInstaller spec file for AI Co-Pilot
# Build: pyinstaller ai_copilot.spec

import os
from pathlib import Path

desktop = Path.home() / "Desktop"

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'anthropic',
        'mss',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'win32gui',
        'win32process',
        'win32api',
        'win32con',
        'psutil',
        'dotenv',
        'sqlite3',
        'tkinter',
        'tkinter.ttk',
        'pystray',
        'pystray._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'IPython'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AI-CoPilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # add icon.ico here if you have one
)
