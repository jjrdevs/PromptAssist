# Testing on Windows

Run-through checklists for verifying the release, especially the first
`cargo tauri build` on a fresh Windows box.

## 0. Prereqs (once)

| Need    | Command                              |
|---------|--------------------------------------|
| Python  | `winget install Python.Python.3.12`  |
| Rust    | `winget install Rustlang.Rust`       |
| Node.js | `winget install OpenJS.NodeJS`       |
| WebView2| `winget install Microsoft.EdgeWebView2Runtime` (auto on Windows 11) |

Open a **new** PowerShell after installs so `PATH` refreshes.

## 1. CLI first (fast, ~90 s)

```powershell
git clone https://github.com/jjrdevs/PromptAssist
cd PromptAssist
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q        # expect 81 passed
.\.venv\Scripts\pip install pyinstaller
.\.venv\Scripts\python -m PyInstaller -y --clean passist.spec
dist\passist.exe --help
dist\passist.exe new test1 --target C:\temp
dist\passist.exe run research test1
dist\passist.exe export test1            # all 6 stages to stdout
```

**Watch for:** the frozen `passist.exe` silently exiting with no output
(= bundled `passist/data/prompts.yaml` not found). If any command prints
a file-not-found-style error, the spec's Data path is wrong — report it.

## 2. GUI dev loop (iterate fast)

```powershell
.\.venv\Scripts\pip install -e .          # so passist is on PATH as a venv bin
cd gui
cargo install tauri-cli --version "^2"
cargo tauri dev
```

Set the env var so the GUI finds the **venv** passist:

```powershell
$env:PROMPTASSIST_BIN = "..\.venv\Scripts\passist.exe"
cargo tauri dev
```

### GUI checklist

- [ ] Window opens; all 6 stages visible with correct F-key labels (F2–F7)
- [ ] Click **Research** → prompt appears in the output box, copied to clipboard
- [ ] Click a different app (e.g. notepad) → press **F2** → prompt auto-pasted
- [ ] **Settings** tab: toggle auto-paste OFF → repeat F2 → clipboard only, no paste
- [ ] **F8** advances to the next stage automatically
- [ ] Tray icon present; **Ctrl+Alt+Q** quits
- [ ] Reopen → feature list and settings survived (state in `%LOCALAPPDATA%\PromptAssist`)
- [ ] If F-keys conflict with your desktop/IDE (F2 Rename, F5 Refresh):
      `passist apply-safe-fallbacks` then check **Settings** shows `Ctrl+Shift+1..6`

## 3. Full release build (what you ship)

```powershell
cd PromptAssist
.\build.ps1
```

Expect, in order:
1. `dist\passist.exe` (~11 MB)
2. `dist\PromptAssist.exe` + `dist\PromptAssist.exe` in `dist\setup\`
3. `PromptAssist-windows.zip`

### Release checklist

- [ ] Copy `dist\setup\` to another folder / USB stick (fresh dir = real test)
- [ ] Double-click `PromptAssist.exe` → window opens
- [ ] It finds `passist.exe` sitting **next to it** (no `PROMPTASSIST_BIN` set, no venv)
- [ ] All 6 stages render in the GUI
- [ ] `passist.exe sync-agent --target <some\repo>` writes 4 agent files

## Things most likely to be broken on first Windows run

| # | Area | What to look for |
|---|------|------------------|
| 1 | **Binary lookup** | GUI can't find `passist.exe` next to the app (recently changed, never Windows-tested) |
| 2 | **Clipboard paste** | Auto-paste fails if your AI tool is in a different desktop/session (RemoteDesktop) |
| 3 | **Hotkeys** | F-key collision with your shell/IDE; use `apply-safe-fallbacks` |
| 4 | **WebView2** | Blank white window = runtime missing |
| 5 | **PyInstaller data** | `passist.exe` prints nothing = data bundle path wrong |
