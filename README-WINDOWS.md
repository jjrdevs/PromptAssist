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

Two .exe files, one folder:

```
PromptAssist/
├─ PromptAssist.exe     # GUI: tray app + shortcut window (F-keys)
├─ passist.exe          # CLI: same features from a terminal
└─ README-USE.md        # how-to for the person using it
```

That's the whole distribution. Nothing else to install, nothing to configure.
The prompts are baked in and live in the same place as your feature store:

```
%LOCALAPPDATA%\PromptAssist\
├─ features.json
├─ settings.json
├─ prompts.yaml
└─ agent_rules.md
```

## Fastest path (5 minutes)

1. Copy the `PromptAssist` folder to your Windows machine (zip/SharePoint/Dropbox/USB).
2. Unzip it if it's a zip. Double-click `PromptAssist.exe`.
3. A tray icon appears with the 6 stages. Press **F2** through **F7** to fire them,
   **F8** auto-advances to the next stage, **F9** pops the window if you lose it,
   **Ctrl+Alt+Q** quits.
4. Your AI coding tool's prompt box already has the next prompt pasted in
   (auto-paste is ON by default; toggle it under **Settings**).

Or, if you prefer the terminal:

```
> passist new my_feature --target C:\myRepo
> passist run research my_feature
> passist run plan my_feature
> passist run check-plan my_feature
> passist run build my_feature
> passist run continue my_feature
> passist run review-code my_feature
```

## Build it yourself (for developers)

You don't need this if you already have the two .exe files. This is for people
**creating** the Windows release from source.

### One-click

```powershell
# On a Windows machine with Rust, Node and Python installed:
cd PromptAssist
.\build.ps1
```

That gives you `dist\PromptAssist.exe`, `dist\passist.exe`, and a shareable zip at
`PromptAssist-windows.zip`.

### Flags

| Flag          | Effect                                     |
|---------------|--------------------------------------------|
| `-SkipGui`    | Only build the CLI (fast, no Rust needed)  |
| `-SkipCli`    | Only build the GUI                         |
| `-NoZip`      | Skip the zip, keep the `dist\setup\` folder |

### Step-by-step (manual)

**Prereqs** — install each before running:

| Package   | Where                          | Notes                              |
|-----------|-------------------------------|------------------------------------|
| Python 3  | python.org / winget           | 3.10+                              |
| Rust      | rustup.rs / winget            | `rustup default stable-x86_64-pc-windows-msvc` |
| Node.js   | nodejs.org / winget           | 18+                                |
| WebView2  | aka.ms/webview2 (already on Win 11; on Win 10 install) | Required for Tauri |

```powershell
# 0. sanity check
python --version
rustc --version
node --version

# 1. one-file CLI (no Rust needed, ~90 s)
pip install pyinstaller
python -m PyInstaller -y --clean passist.spec
#  -> dist\passist.exe

# 2. GUI (takes 2–5 minutes, Rust + Node)
cd gui
cargo tauri build
#  -> ..\dist\PromptAssist.exe

# 3. assemble the share folder
mkdir dist\setup
copy dist\passist.exe        dist\setup\
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

