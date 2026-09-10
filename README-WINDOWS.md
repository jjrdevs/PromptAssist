# PromptAssist for Windows

Six-stage prompt runner for AI coding (GitHub Copilot Workspace, Claude Code, Gemini CLI,
Codex, or any chat tool — same prompts for every one).

- Stage 1  **Research**     — understand the feature before touching code
- Stage 2  **Plan**         — write a plan only; no implementation
- Stage 3  **Check plan**   — adversarial review against the spec
- Stage 4  **Build**        — implement per the checked plan
- Stage 5  **Continue**     — pick up where any session left off
- Stage 6  **Review code**  — final audit against the original feature & plan

## Who this is for

You already have an AI coding tool. PromptAssist hands you a **paste-ready prompt**
for each stage — you paste it into your tool's prompt box. Your tool does the actual
coding. PromptAssist does not call any LLM itself.

## What ships

Two .exe files and a folder:

```
PromptAssist/
├─ passist_gui_launcher.exe  # GUI: Tkinter window with Stages + Settings tabs
├─ passist.exe               # CLI: same features from a terminal
└─ README-WINDOWS.md         # this guide
```

The prompts and settings live in your user folder:

```
%LOCALAPPDATA%\PromptAssist\
├─ features.json
├─ settings.json
```

## Fastest path (5 minutes)

### Using the GUI launcher

1. Copy the `PromptAssist` folder to your Windows machine (zip/SharePoint/Dropbox/USB).
2. Unzip it if it's a zip. Double-click `passist_gui_launcher.exe` (in the `dist/` folder).
3. The PromptAssist window opens with:
   - **Stages tab**: Shows 6 stage buttons (Research, Plan, Check plan, Build, Continue, Review code)
   - **Settings tab**: Configure hotkeys and toggle auto-paste
4. Enter a feature name and click a stage button, or press the hotkey:
   - **Shift+F2** through **Shift+F7** for the 6 stages (default)
   - **Ctrl+Alt+Q** to quit
5. Your AI coding tool's prompt box already has the next prompt pasted in
   (auto-paste is ON by default; toggle it under **Settings**).

### Using the terminal

If you prefer the command line:

```powershell
> passist new my_feature --target C:\myRepo
> passist run research my_feature
> passist run plan my_feature
> passist run check-plan my_feature
> passist run build my_feature
> passist run continue my_feature
> passist run review-code my_feature
```

## Customizing hotkeys

Click the **Settings** tab in the launcher to:
- **Change any hotkey** — type a new combo (e.g., `Ctrl+Shift+1`, `Ctrl+Alt+R`)
- **Toggle auto-paste** — auto-paste into your AI tool's prompt box (default: ON)
- **Save hotkeys** — write changes to disk in one go (no terminal pop-ups)
- **Use safe fallbacks** — apply pre-configured alternatives if your defaults conflict
- **Reset to defaults** — restore the original Shift+F hotkeys

## Build it yourself (for developers)

You don't need this if you already have the .exe files. This is for developers
**creating** the Windows release from source.

### Quick build (GUI + CLI)

```powershell
# On a Windows machine with Python 3.10+ installed:
cd PromptAssist
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\pip install pyinstaller keyboard

# Build CLI
.\.venv\Scripts\python -m PyInstaller -y --clean --noconsole --onefile passist.spec

# Build GUI launcher
.\.venv\Scripts\python -m PyInstaller -y --clean --noconsole --onefile passist_gui_launcher.py
```

That gives you:
- `dist\passist.exe` (core CLI)
- `dist\passist_gui_launcher.exe` (Tkinter GUI wrapper)

Both are self-contained and need no runtime.

### Manual steps

```powershell
# 1. Set up the environment
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
pip install pyinstaller keyboard

# 2. Run tests to verify
pytest -q

# 3. Build the CLI
python -m PyInstaller -y --clean --noconsole --onefile passist.spec
# -> dist\passist.exe

# 4. Build the GUI launcher
python -m PyInstaller -y --clean --noconsole --onefile passist_gui_launcher.py
# -> dist\passist_gui_launcher.exe

# 5. Zip for sharing
Compress-Archive -Path dist -DestinationPath PromptAssist-windows.zip
```


copy dist\PromptAssist.exe   dist\setup\
#  (optional: also copy a short README-USE.md there — see build.ps1)

# 4. zip it and ship
Compress-Archive dist\setup PromptAssist-windows.zip
```

### Troubleshooting

| Symptom                                        | Fix                                                     |
|------------------------------------------------|---------------------------------------------------------|
| `cargo: command not found`                     | `winget install Rustlang.Rust` and open a new shell     |
| `node: command not found`                      | `winget install OpenJS.NodeJS` and open a new shell     |
| Tauri: "webview2 runtime not found"            | `winget install Microsoft.EdgeWebView2Runtime`          |
| PyInstaller: "Microsoft Visual C++ 14.0 required"| `winget install Microsoft.VCRedist.2015+.x64`         |
| Antivirus flags `passist.exe`                  | One-file PyInstaller payloads get scanned; allow it once |

