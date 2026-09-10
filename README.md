# PromptAssist

A lightweight Windows desktop utility for the 6-stage AI-coding workflow.

Type a feature name once; every stage prompt (Research, Plan, Check plan,
Build, Continue, Review code) auto-renders from one shared template file and
is fired by a configurable F-key shortcut, a tray icon, or a GUI button. The
tool is a pure delivery/rendering mechanism — it makes **no LLM calls**.

## Two deliverables

| Piece | What it is | Runs |
|---|---|---|
| **`passist` CLI** | Python package (stdlib + PyYAML). Renders prompts, manages features/hotkeys, syncs agent files. | anywhere with Python 3.10+ |
| **GUI (Tauri 2)** | Tray app + window wrapping the CLI. Single render path. | Windows (build) / any OS (run) |

The GUI **delegates every render to the CLI** — there is exactly one
implementation of the prompt logic (the Python core).

## Layout
```
PromptAssist/
  passist/            # Python core (single render source of truth)
    __main__.py      #   argparse CLI
    render.py        #   template engine
    storage.py       #   features.json / settings.json
    hotkeys.py       #   combo parse, conflicts, safe fallbacks
    agent_sync.py    #   one agent_rules.md -> CLAUDE/AGENTS/copilot/GEMINI
    data/prompts.yaml  # the 6 stage templates (edit to taste)
    data/agent_rules.md  # agent-file source
  gui/
    src/{lib,cli,shortcuts}.rs   # Tauri backend (delegates to passist)
    frontend/              # index.html + app.js + styles.css (no build step)
    icons/                 # PNG + .ico app/tray icons
    tauri.conf.json  capabilities/default.json  Cargo.toml  build.rs
  tests/             # 81 pytest cases
  README.md                  # this file
  README-WINDOWS.md          # Windows install/share steps
  BUILD_WINDOWS.md           # how to build the GUI (Tauri 2) on Windows
```

## Install (CLI — any OS)

```bash
cd PromptAssist
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/passist --help
```

## Quick start
```bash
# 1. Register a feature (one feature = one target repo)
passist new add_session_logging --target /path/to/repo

# 2. Fire a stage — prompt rendered to stdout, copied to clipboard
passist run research add_session_logging
passist run build

# 3. See what's bound / list features
passist list-bindings
passist ls

# 4. Write agent files into the target repo
passist sync-agent --target /path/to/repo
```

`run <stage>` omits the feature name when you have a single/active feature.

## GUI (Tauri 2)

The GUI is a thin shell over the CLI: it never renders prompts itself. Open it
with the tray, click a stage (or its F-key), and the prompt is copied/pasted
straight into whatever you had focused.

**Build target: Windows.** This box has no Rust/node/WebKit toolchain and
Tauri does not cross-compile to Windows, so build on a Windows machine:

```powershell
# see BUILD_WINDOWS.md for the full walk-through + WebView2 prerequisites
cargo install tauri-cli --version "^2"
cd gui
cargo tauri dev     # iterate
cargo tauri build   # release: target\release\promptassist-gui.exe
```

The frontend ships as plain HTML/CSS/JS under `gui/frontend/` (Tauri serves it
statically, **no bundler**). It auto-detects Tauri; opened in a plain browser
it falls back to a labelled **mock mode** so the UI design is reviewable
headless.

## Configuration
State lives under the user-config directory
(`PROMPTASSIST_DATA_DIR` → `%LOCALAPPDATA%\PromptAssist` on Windows,
`~/.config/promptassist` elsewhere):

- **`features.json`** — registered features (name, target repo, last-fired).
- **`settings.json`** — `auto_paste` toggle + per-stage hotkeys.
- **`passist/data/prompts.yaml`** & **`data/agent_rules.md`** — editable
  templates (override location with `--assets-dir`).

Hotkeys default to F2–F7 for the six stages (plus F8 next, F9 window,
`Ctrl+Alt+Q` quit). Because Windows F-keys collide with OS actions (F2 Rename,
F5 Refresh), a **safe fallback** set is one click away:
`passist apply-safe-fallbacks` → `Ctrl+Shift+1..6`.

```bash
passist bind review-code F7          # rebind one stage
passist bind build --clear           # unbind (button/tray only)
passist list-bindings                # table + live conflict detection
passist show                         # dump effective settings.json
```

## Editing the prompts

The whole workflow is driven by two data files — no code change needed:

- `prompts.yaml` — the 6 stage bodies (use `{feature_name}`,
  `{target}`, `{agent_name}` placeholders).
- `agent_rules.md` — one source that syncs into `CLAUDE.md`, `AGENTS.md`,
  `.github/copilot-instructions.md`, and `GEMINI.md`.

## Testing

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q      # 81 tests
```

Tests run the real CLI in a subprocess under an isolated
`PROMPTASSIST_DATA_DIR`, so they never touch your live state.

## Design invariants

1. **One render source** — the CLI's `render_stage()` is the only template
   engine; the GUI and every other surface call it.
2. **No LLM in the loop** — the tool emits text; pasting is your choice.
3. **Explicit stage boundaries** — each prompt names its stage and forbids
   starting the next one.
4. **Windows first** — clipboard + auto-paste + hotkey UX is tuned for the
   desktop, not a terminal.

See `PLAN.md` for research, risk table, and acceptance criteria.


