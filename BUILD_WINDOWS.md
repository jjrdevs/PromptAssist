# Building the PromptAssist GUI (Windows)

The GUI is a [Tauri 2](https://tauri.app/) desktop app that shells out to the
`passist` Python CLI. It is built natively on the target OS — **no cross-compile**
supported. This box (Linux, headless) has no Rust/Node/WebKit toolchain and
Tauri will not cross-compile to Windows, so build on a Windows machine.

## Prerequisites

- **Windows 10/11** x64 (or Windows Server 2019+ where WebView2 is available).
- **WebView2** — the runtime Tauri 2 uses for its webview. Usually pre-installed
  on Win11; on Win10 check for "Microsoft Edge WebView2 Runtime" under
  *Apps > Installed apps*, or install it from
  <https://developer.microsoft.com/en-us/microsoft-edge/webview2/>.
- **Rust toolchain** 1.75+ via <https://rustup.rs> — `rustup install stable-msvc`
  (the MSVC toolchain is the default and best-supported for Tauri on Windows).
- **Microsoft Visual Studio C++ Build Tools** (x64) with the "Desktop development
  with C++" workload — Tauri links against MSVC.
- **NSIS 3.0** (installed separately, optional for NSIS installer flavour —
  default Tauri 2 uses the WiX MSI installer).
- **Python 3.10+** on the PATH (or wherever the GUI can find `passist`).
  The GUI locates `passist` via the env vars below.

## Install the Python CLI

```powershell
# in the repo root
python -m venv .venv
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
passist --help    # should print usage
```

The GUI spawns `passist` as a subprocess. By default it looks on the PATH;
you can override with `PROMPTASSIST_BIN` (absolute path to the `passist`
script or `python.exe` running the package).

## Iterate in dev mode

```powershell
# from the gui/ directory
cargo install tauri-cli --version "^2"
# (or: winget install OpenTofu.TauriCli — not required)

cargo tauri dev
```

`cargo tauri dev` rebuilds Rust and reloads the HTML on save. On first run
Tauri compiles the entire dependency tree (~5–10 min) — subsequent runs are
seconds. The window opens with the three tabs you implemented (Run / Bindings /
Settings).

## Ship a release

```powershell
cargo tauri build
```

Output:

- `target/release/promptassist-gui.exe`        — portable double-click app
- `target/release/bundle/msi/*.msi`            — Windows MSI installer
- `target/release/bundle/nsis/*.exe`           — NSIS installer (if enabled)

Distribute the `.exe` for a single-file drop, or the `.msi` for a proper
Start-menu + desktop + uninstall experience.

## Packaging the CLI alongside the GUI

If you bundle the Python CLI for distribution, either:

1. **Ship the `.venv` folder** (simple, works offline, big) — and set
   `PROMPTASSIST_BIN=%LOCALAPPDATA%\PromptAssist\.venv\Scripts\passist.exe`.
2. **PyInstaller one-file** (small, requires `pip install pyinstaller` and
   `pyinstaller --onefile passist/__main__.py --name passist`) — and set
   `PROMPTASSIST_BIN=%LOCALAPPDATA%\PromptAssist\passist.exe`.

Both work; PyInstaller is smaller and self-contained.

## Verifying a fresh install on Windows

```powershell
# from an empty profile, after copying the app to %LOCALAPPDATA%
$env:PROMPTASSIST_DATA_DIR = "$env:LOCALAPPDATA\PromptAssist"
& .\promptassist-gui.exe
# then use the Settings tab to confirm the hotkeys are registered —
# they will appear in a system-wide hotkey tester of your choice, or just try F2
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `error: failed to run custom build command for webview2-com-sys` | WebView2 runtime not installed — install Edge WebView2 Runtime (Evergreen, from the link above) and reboot. |
| `link.exe: not found` | VS Build Tools "Desktop C++" workload missing — install it. |
| `cannot find crate tokio` / compile times | Expected on first build. `cargo clean target` + rebuild. |
| `failed to spawn passist` | GUI can't find `passist` — set `PROMPTASSIST_BIN` to the absolute path or add the venv's `Scripts/` to PATH. |
| `RegisterHotKey failed: 1409` (ERROR_HOTKEY_ALREADY_REGISTERED) | The combo is already bound to something else — use the Bindings tab to unbind, or apply `passist apply-safe-fallbacks`. |
| `tauri command not found` | Use `cargo tauri dev` / `cargo tauri build` (Tauri CLI), not bare `cargo run` — the CLI wires the plugin + capabilities correctly. |
| Icons missing / tray blank | `gui/icons/icon.ico` and `icon-256.png` must exist — regenerate if missing with the Python script in `gen_icons.py` (or any tool that can make .ico). |
| App runs but the tray icon doesn't show | Windows taskbar overflow — look under the `^` chevron in the tray. |

## Uninstall

MSI installers register cleanly with Add/Remove Programs. The portable
`.exe` has no registry footprint; delete the file and optionally
`%LOCALAPPDATA%\PromptAssist` (your `features.json` + `settings.json`).
