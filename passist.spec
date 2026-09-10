# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for a self-contained ONE-FILE `passist` CLI.
#
#   Build:  python -m PyInstaller passist.spec
#   Result: dist/passist          (dist/passist.exe on Windows)
#
# One file, zero Python required, zero config files — prompts.yaml and
# agent_rules.md ride along inside the bundle (Data([...], "passist/data")
# matches the sys._MEIPASS lookup in passist/storage.py:assets_dir()).
#
#   hiddenimports=["yaml"]  ->  keeps the PyYAML C-extension from shaking out
#   upx=False               ->  smaller, and avoids UPX-antivirus false-positives
#
# Trade-off: one-file unpacks its payload on every launch, so first run is a
# little slower than one-folder. For a "send this one .exe to someone" story,
# that's the right call.

a = Analysis(
    ["passist_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=[("passist/data", "passist/data")],
    hiddenimports=["passist", "passist.__main__", "passist.render", "passist.storage",
                   "passist.models", "passist.settings", "passist.hotkeys",
                   "passist.agent_sync", "passist.clipboard", "yaml"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="passist",                    # -> passist.exe on Windows
    debug=False,
    strip=False,
    upx=False,
    console=True,
    onefile=True,                      # single self-contained executable
)
