# PromptAssist — Research & Build Plan (Windows)

*Researched & corrected 2026-09-10, for jjrdevs. Target audience: **Windows** developers. Source draft: `/home/jjrdev/.hermes/webui/attachments/7cfc947e8153/pasted-text-2026-09-10_12-31-02-320.md`.*

---

## 0. Executive summary

**PromptAssist is a small Windows desktop utility (tray app + optional window) that turns a 6-stage LLM-coding prompt workflow into one keypress each.** You enter a `feature_name` once; after that every stage is reached by a **user-configurable global shortcut** or a button. The correct — already name-filled — prompt lands on your clipboard (and, if you enable it, pastes itself) and you drop it into Copilot / Claude / any agent.

Your 7-prompt draft is already well-aligned with current agentic-coding best practice (research → plan → self-audit → implement → resume → verify). The work is:
1. **Small prompt hygiene fixes** — consistent placeholder, a stop-rule header in every stage, explicit artifact paths.
2. **Merge the two resume stages into one** → 6 stages, not 7.
3. **Ship the agent-file under the right filename(s)** for the toolchain (Claude Code / Copilot / Gemini).
4. **Build the delivery layer**: Windows tray app, **configurable hotkeys as a first-class feature in a Settings tab**, single `.exe` install, plus a Python CLI for power users.
5. All state is local files — no cloud, no accounts, editable by hand.

Recommended stack: **Tauri 2** (Rust core + WebKit, ~15–25 MB `.exe`, low RAM, first-class `GlobalShortcut` plugin, tray support) + a tiny **Python CLI** sharing the same render code path. Data lives in `%LOCALAPPDATA%\PromptAssist\` as plain-text files.

---

## 1. Research findings → how they shape the design

### 1.1. Prompt content is already best-practice ✅

Multiple independent 2025/2026 sources (AddyOsmani's 2026 workflow essay, the Refine-Plan-Act pattern, r/AI_Agents' producer/verifier pair, Kestra's prompt-chaining guide) all converge on the shape you already have:

| Your stage | Industry name | Match |
|---|---|---|
| 1. Research | Refine / Research | ✅ |
| 2. Create plan | Plan (with plan-file output) | ✅ |
| 3. Audit plan | Self-review / critique step | ✅ explicit |
| 4. Begin development | Act with "explain before edit" | ✅ |
| 5. Continue | Resume-from-state | ✅ |
| 6. Audit implementation | Verifier/auditor pass | ✅ best to keep as a *separate* prompt — you do |
| 7. Review/continue | Resume step #2 | ⚠ redundant with 5 |

Two findings that reinforce your structure:

1. **The plan file is the single source of truth across sessions.** Kestra's guide and APXLM's state-management chapter both call "state via a persistent plan document" a core technique. Your `/docs/development/[feature]_development_plan.md` is exactly that. Keep it sacred — it's what lets a fresh agent session later resume correctly.
2. **Producer/verifier separation is the highest-leverage pattern in agentic coding.** Your prompts 3 and 6 already do this as pure read-only audits. Keep both strictly forbid from writing code.

### 1.2. Agent file: one source, several names

Research consensus (VS Code Custom Instructions docs, GitHub Blog 2025-08-28 Copilot-coding-agent + AGENTS.md changelog, 2025/26 "AGENTS.md vs CLAUDE.md" threads):

- `AGENTS.md` — emerging cross-vendor standard (VS Code, Copilot, Claude Code fallback).
- `CLAUDE.md` — Claude Code and any Claude-based agent; VS Code reads it too when `chat.useClaudeMdFile` is enabled.
- `.github/copilot-instructions.md` — GitHub-hosted Copilot agent.
- `GEMINI.md` — Gemini CLI.

**Decision:** one source `agent_rules.md` inside PromptAssist; a `passist sync-agent` command emits it byte-identical (plus a one-line tool-specific header) to all four names in the target repo. No drift, no copy-paste.

### 1.3. Windows-native mechanics

| Concern | Windows answer |
|---|---|
| Global hotkeys | Win32 `RegisterHotKey` — native, reliable, first-class. Tauri exposes it via the official `tauri-plugin-global-shortcut`. |
| Conflict detection | If `RegisterHotKey` fails with `ERROR_HOTKEY_REGISTERED` (0x0312) or `ERROR_ACCESS_DENIED`, the API tells us; we surface an inline "already in use — pick another" prompt and log to UI. |
| Clipboard | `SetClipboardData` / `Clipboard.SetDataObject` — trivial, always works. |
| Synthetic Ctrl+V | Win32 `SendInput` from any native process — reliable when the target window is foreground. Tauri: `GlobalShortcut` + a tiny FFI call or use `robot`-style library in the Rust core; Python CLI uses `pyautogui`. |
| Tray icon | `Shell_NotifyIcon` / Tauri `TrayIcon` API. |
| Single-file install | Tauri MSI/NSIS installer (default) or bare `.exe` in `C:\Program Files\PromptAssist\` — both fine. |
| Autostart | Optional; `HKCU\...\Run` registry key, toggle in Settings. |
| Distribution | GitHub Releases with an MSI; document the SmartScreen "More info → Run" path for unsigned builds (or sign once we have a cert). |

There is no Wayland-style friction on Windows. Synthetic paste works. Hotkeys work. This is a much more forgiving platform for the design than Linux.

### 1.4. State model

Keep state **file-based** (Kestra + APXLM agree): the *plan file* is the state. In PromptAssist's `%LOCALAPPDATA%\PromptAssist\features\<id>.json` we store:
- `feature_name` (normalized)
- `current_stage` (1..6)
- `created_at`, `updated_at`
- `target_repo` (absolute path where the docs/development folder lives)
- artifact paths (derived but cached)

CLI and GUI both read/write the same file. A fresh agent session reads the *plan file*. Two consumers, one source of truth, no API.

---

## 2. Prompt-level improvements (apply in Phase 0)

Small, mechanical fixes to the draft:

| # | Issue | Fix |
|---|---|---|
| 1 | Placeholder inconsistency: `[INSERT FEATURE]` in 1 & 6, `[feature_name]` in 2, 4, 5, 7. | Standardize on `{feature_name}` (one token, one regex). |
| 2 | Stages 5 and 7 are near-duplicates. | **Merge into one stage: "Resume & Continue"** → 6 stages, not 7. |
| 3 | Stop-rules sit at the bottom of each prompt; agents drift. | Add a **2-line header** to every stage: *"You are executing STAGE N/6. Before writing a single code line or file, confirm the stage boundary in one sentence. Then stop when the deliverable above is produced."* (Documented as the highest-impact adherence fix.) |
| 4 | Feature name isn't normalized, so path templates can drift. | Rule (agent file): *feature names are `lowercase_snake_case`*. The **app** normalizes before rendering, then the placeholder is always pre-normalized. |
| 5 | Audit stages 3 and 6 don't say where to write. | Add explicit paths: `_audit_plan.md` (stage 3), `_audit_impl.md` (stage 6). Symmetric with the plan path. Final layout: `<repo>/docs/development/{feature_name}_.md` for all four artifacts. |
| 6 | The word "Copilot" is hard-coded in the draft's preamble. | Make it `{agent_name}` (a variable, configurable per workspace). Default: "your AI coding agent". |
| 7 | Prompts 1 and 4 both open with the same "Using: research / docs / current impl" list. | Extract into a small preamble the **app injects**, so there's one place to edit. |

**Resulting 6 stages (final) — verb-first, intent-aligned names:**

| # | Name | What it does (user phrasing) | Key artifact (in repo) | Read-only? |
|---|---|---|---|---|
| 1 | **Research** | "Find out what exists before we decide anything." | `docs/development/{feature_name}_research.md` | ✅ no — discovery only |
| 2 | **Plan** | "Write the plan for exactly this change." | `docs/development/{feature_name}_plan.md` | ✅ no — no code |
| 3 | **Check plan** | "Find gaps, risks, missing edge cases *before* any code." | `docs/development/{feature_name}_plan-check.md` | **Read-only** |
| 4 | **Build** | "Do the work, following the plan." | code + `docs/development/{feature_name}_progress.md` | ❌ writes code |
| 5 | **Continue** | "Pick up where Build left off, from the progress file." | continues Build via `_progress.md` | ❌ writes code |
| 6 | **Review code** | "Check what we built actually matches the plan." | `docs/development/{feature_name}_code-review.md` | **Read-only** |

**Naming rules** (apply to UI buttons, CLI verbs, settings keys, `prompts.yaml` stage IDs, tray menu items, and the file names above):
- **Verb-first, lowercase, hyphenated where two words.** `research`, `plan`, `check-plan`, `build`, `continue`, `review-code`.
- **Never `stage_1`, `stage_3`, …** in any user-facing surface. Numeric IDs may exist internally (e.g. in `features/*.json` for ordering) but never leak out.
- **The intent phrase above** appears in UI tooltips, tray-menu hints, and `passist run <name> --help`. Users never have to translate "stage 4" to figure out what it does.
- **File names match the verb**: `research.md`, `plan.md`, `plan-check.md`, `progress.md`, `code-review.md`. One-to-one with stage names.

---

## 3. Product design

### 3.1. Surfaces (two)

1. **Windows app** (the primary surface): tray icon + small window (one input, six stage buttons, settings tab, preview pane). Runs minimized to tray; global hotkeys work whether the window is open or not.
2. **CLI** (`passist.exe`, built with PyInstaller): `new`, `run <stage>` (where `<stage>` is one of `research | plan | check-plan | build | continue | review-code`), `ls`, `export`, `sync-agent`, `bind <stage> <combo>`, `list-bindings`. Same render code path as the GUI — unit-tested, shared.

### 3.2. The six stage buttons (window)

```
┌─ PromptAssist ───────────────────────────────────────── [—][□][×] ┐
│  feature: [add_session_logging        ]  [new]  [open target]  │
│  target  : [C:\dev\myapp                          ]              │
│                                                                  │
│  ▸ Research     (done)                     [F2]                 │
│  ▸ Plan         (done)                     [F3]                 │
│  ▸ Check plan ◂— next (highlighted)      [F4]  ◂— press to fire│
│  ▸ Build                                   [F5]                 │
│  ▸ Continue                                [F6]                 │
│  ▸ Review code                             [F7]                 │
│                                                                  │
│  ┌── preview (read-only, monospace, scrollable) ──────────┐    │
│  │ CHECK-PLAN. Confirm in one sentence that you're only  │    │
│  │ reading docs/development/add_session_logging_plan.md — │    │
│  │ do not modify any file. Then list gaps, risks, and    │    │
│  │ missing edge cases.                                    │    │
│  │ …(full rendered prompt)…                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  [ Fire (F4) — copy + paste ]  [ Settings ]                    │
└──────────────────────────────────────────────────────────────────┘
```

**One-click = copy-and-paste** by default (Windows makes this reliable). If the user unchecks "auto-paste" in Settings, it's copy-only with a subtle "pasted to clipboard — go paste" toast.

### 3.3. Hotkeys — CORE FEATURE (F-keys by default)

**Each stage has a bound, user-reconfigurable global hotkey** — F-key by default (one-press, muscle-memory-friendly), safe-fallback modifier combos available.

| Action | Default (F-key) | Safe fallback | Rebindable? |
|---|---|---|---|
| **Research**  | `F2` | `Ctrl+Shift+1` | ✅ |
| **Plan**      | `F3` | `Ctrl+Shift+2` | ✅ |
| **Check plan**| `F4` | `Ctrl+Shift+3` | ✅ |
| **Build**     | `F5` | `Ctrl+Shift+4` | ✅ |
| **Continue**  | `F6` | `Ctrl+Shift+5` | ✅ |
| **Review code**| `F7` | `Ctrl+Shift+6` | ✅ |
| **Next (smart)**  — jump to the recommended stage | `F8` | `Ctrl+Shift+N` | ✅ |
| **Open window to next stage** | `F9` | `Ctrl+Shift+O` | ✅ |
| **Toggle auto-paste** | (button only) | — | — |
| **Quit PromptAssist** | `Ctrl+Alt+Q` | (keep as-is) | ✅ |

**Why F-keys by default:**
- One-press, always on the keyboard, zero chord memorization.
- In most Windows apps F2-F7 are *not* heavily used when a text box is *not* focused — and this is a tray/launcher use-case, not a text-editing one. F1 (Help) and F12 dev-tool are avoided.
- If the user is inside an app that *does* own that F-key (e.g. VS Code owns a lot), the "safe fallback" column is the pre-populated one-click alternative — `Ctrl+Shift+<digit>` has near-zero collision in Windows apps.
- **All defaults are overridable** in Settings or `settings.json`; F-keys are just the starting point.

**Behavior:**
- Hotkeys are **system-global** (Win32 `RegisterHotKey`) — they fire even if PromptAssist's window is hidden or another app is focused.
- On fire: render the intent-named stage for the active feature → put on clipboard → (if auto-paste ON) send `Ctrl+V` to the foreground window. A toast in the corner says "📋 `check-plan` copied + pasted" (or "copied — paste when ready" when auto-paste is OFF).
- If a default F-key is already taken by another app, `RegisterHotKey` fails at startup for that one; the Settings tab shows a red dot and the Settings tab automatically suggests the "safe fallback" combo as a pre-fill for that row. User accepts or types another.
- Users can **disable** any hotkey (click `×`), leaving the button-only path.
- **Any** valid GlobalShortcut combo is accepted (modifiers + char key, F-keys, numpad). Multi-modifier and single-key both work.
- Conflict policy: **fail-soft**. If the OS or another app owns the combo, the app never crashes and never silently overwrites; it surfaces it and lets the user pick another.

**Settings tab** (this is a real tab, not a config-file-only fallback):

```
┌─ Settings ───────────────────────────────────────── [×] ┐
│  ▸ General   ▸ Hotkeys  ▸ Features   ▸ About           │
│                                                          │
│  Hotkeys                                                    │
│  ┌────────────────┬────────────────────┬────────────┐  │
│  │ Action          │ Default            │ Current      │  │
│  ├────────────────────────────────────────────────────┤  │
│  │ Research        │ F2                 │ [ F2   ] [×] │  │
│  │ Plan            │ F3                 │ [ F3   ] [×] │  │
│  │ Check plan      │ F4                 │ [ F4   ] [×] │  │  ◂ ← red dot
│  │ Build           │ F5                 │ [ F5   ] [×] │  │  if F4 taken
│  │ Continue        │ F6                 │ [ F6   ] [×] │  │  → F4 row shows a
│  │ Review code     │ F7                 │ [ F7   ] [×] │  │  suggested
│  │ Next (smart)    │ F8                 │ [ F8   ] [×] │  │  Ctrl+Shift+3
│  │ Open window     │ F9                 │ [ F9   ] [×] │  │
│  │ Quit            │ Ctrl+Alt+Q         │ [Ctrl+Alt+Q][×]│ │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  [Restore all defaults]   [Apply safe fallbacks]        │
│                                                          │
│  ✎ To change: click a Current box, then tap your combo. │
│    A red dot means that combo is already taken by another│
│    app; "Apply safe fallbacks" swaps them all to         │
│    Ctrl+Shift+1..9 in one click.                         │
└──────────────────────────────────────────────────────────┘
```

**Editability without UI:** the settings tab **is** the same JSON under the hood. The human path is the Settings tab; the *advanced/automation* path is:

```
%LOCALAPPDATA%\PromptAssist\settings.json
{
  "auto_paste": true,
  "hotkeys": {
    "research":     "F2",
    "plan":         "F3",
    "check-plan":   "F4",
    "build":        "F5",
    "continue":     "F6",
    "review-code":  "F7",
    "next":         "F8",
    "open-window":  "F9",
    "quit":         "Ctrl+Alt+Q"
  },
  "safe_fallbacks": {
    "research":     "Ctrl+Shift+1",
    "plan":         "Ctrl+Shift+2",
    "check-plan":   "Ctrl+Shift+3",
    "build":        "Ctrl+Shift+4",
    "continue":     "Ctrl+Shift+5",
    "review-code":  "Ctrl+Shift+6",
    "next":         "Ctrl+Shift+N",
    "open-window":  "Ctrl+Shift+O"
  },
  "on_conflict": "fail_soft",
  "start_with_windows": true,
  "active_feature": "add_session_logging"
}
```

Settings tab writes it; editing it by hand triggers a hotkey re-registration on next startup. **Two edit paths — one source of truth.** Satisfies both "Settings tab" and "very easy to edit file" requirements.

### 3.4. Data layout on disk

```
%LOCALAPPDATA%\PromptAssist\
├─ settings.json              ← hotkeys, toggles, active feature
├─ prompts.yaml               ← 6 stage templates (plain YAML, diff-able)
├─ agent_rules.md             ← single source for agent file
├─ features/
│   ├─ add_session_logging.json
│   └─ checkout_flow.json
└─ history/                   ← append-only log of every prompt render
   └─ 2026-09-10.log
```

`prompts.yaml` is the **single source of truth** for the 6 stage templates. GUI, CLI, and any future WebUI extension all read this one file. No drift, no re-implementation.

### 3.5. Acceptance criteria (v1)

- [ ] Install on a clean Windows 11 machine via `PromptAssistSetup.exe`; app shows tray icon; Settings tab opens.
- [ ] Create a feature "add_session_logging" with a target repo path; `passist run check-plan add_session_logging` prints the fully-rendered Check-plan prompt (name substituted, paths filled, stop-rule header present).
- [ ] Press `F4` with a text editor focused; the rendered prompt lands in the clipboard and is pasted (Ctrl+V fires). With "auto-paste" OFF: clipboard only, with a toast.
- [ ] Rebind `check-plan` from `F4` to `Ctrl+Shift+P` in Settings tab; the new combo works and the old one no longer fires; "Apply safe fallbacks" resets it to `Ctrl+Shift+3`.
- [ ] Edit `settings.json` by hand to change a hotkey; next startup loads it.
- [ ] Feature state persists across restart and across user sessions; "next recommended stage" advances as artifacts appear in `docs/development/`.
- [ ] `passist sync-agent` writes `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, `GEMINI.md` into the target repo; bodies byte-identical, one-line tool header differences only.
- [ ] `RegisterHotKey` failure (e.g. another app holds it) surfaces as a red dot on that Settings tab row, not a crash.
- [ ] UI and CLI share one render function, covered by ≥ 15 unit tests (`{feature_name}` substitution, stop-rule presence, path formatting, hotkey parsing, settings round-trip).

### 3.6. Non-goals for v1

- No cloud / no accounts / no sync.
- No LLM call from the app — rendering is template-only; the agent does the thinking.
- No direct injection into a *specific* tool's chat widget (that's v2, per tool: VS Code extension, Copilot WebUI, etc.).
- No multi-user / no team rollout.
- No Electron.
- No macOS / Linux target. (CLI is portable; GUI is Windows-first.)

---

## 4. Build phases (each shippable)

| Phase | Deliverable | Effort | Exit test |
|---|---|---|---|
| **0** | Fixed 6-stage `prompts.yaml` + `agent_rules.md` (from §2 fixes) committed to this repo. | 0.5 d | Human reads; 6 named stages, one `{feature_name}` placeholder, stop-rule header in all. |
| **1** | Python CLI (`passist`): `new`, `run <stage>`, `ls`, `export`, `sync-agent`, `bind <stage> <combo>`, `list-bindings`. No GUI. Unit-tested render path. | 0.5 d | `passist run check-plan add_session_logging \| clip` yields the correct rendered text. |
| **2** | Tauri 2 app (Rust core + plain HTML/JS frontend). Reads/writes the same `settings.json` + `features/*.json` + `prompts.yaml`. Six stage buttons + preview + feature/target input. | 0.75 d | Click "Check plan" in GUI → clipboard gets the rendered prompt (verify via `clip`). |
| **3** | **Hotkeys v1**: register all F-key defaults via `tauri-plugin-global-shortcut`. On fire: render → copy → (optional) paste. Red-dot on conflict; safe-fallback suggestion. | 0.5 d | Press `F4` from any focused app; clipboard gets the `check-plan` prompt for the active feature. |
| **4** | **Settings tab**: General (auto-paste, launch-on-startup), Hotkeys (rebind / disable / restore / apply-safe-fallbacks), Features (active), About (version, links). Writes `settings.json`; reads it on start. | 0.5 d | Rebind `check-plan` to `Ctrl+Shift+P` in UI; new combo fires; old one no-ops; file shows the change; "Apply safe fallbacks" reverts. |
| **5** | Auto-paste via Win32 `SendInput`; graceful fallback to copy-only when target window not focused (toast explains). | 0.25 d | Toggle ON → one click in UI pastes into a VS Code input box. |
| **6** | Packaging: NSIS installer `PromptAssistSetup.exe`; README + `README.md` doc; `agent_rules.md` sync demonstrated in a sample repo. | 0.5 d | Clean Windows machine: install → create feature → walk all 6 stages → verify artifacts appear in `docs/development/`. |

Total ≈ **3.5 working days** + 0.5 d buffer for Windows-side E2E on a real machine.

---

## 5. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Bare F-key clashes with another app (F2 = rename in Explorer, F5 = refresh in some apps, F12 = dev tools) | Med | Med | "Safe fallbacks" one-click button + per-row red dot on conflict; fail-soft on `RegisterHotKey` error; never crash; suggest `Ctrl+Shift+N`. |
| Windows SmartScreen flags unsigned `.exe` on first run | High (first run) | Low | Publish via GitHub Releases; doc "More info → Run once". Long term: code-sign. |
| User has two PromptAssist instances | Low | Med | Single-instance mutex in Rust core; second launch just brings the tray/window to front. |
| Agent ignores the stop-rule headers mid-session (documented failure mode) | Med | High | Per-stage "confirm in one sentence" header + producer/verifier split (Check plan & Review code stay strictly read-only) + intent-aligned names reduce stage-drift. |
| Prompt / CLI / GUI drift | Med | Med | One `prompts.yaml` + one render function + intent-aligned names shared across all surfaces; ≥ 15 unit tests. |
| Agent-file fork (`CLAUDE.md` vs `AGENTS.md`, etc.) rots | Med | Low | One `agent_rules.md` source; `passist sync-agent` regenerates all four names. |
| User's target repo has no `docs/development/` dir yet | Low | Low | App detects on first write and creates the folder (consent prompt once). |
| App becomes "just another tray icon" users forget | Med | Low | Next-stage badge on tray icon + F-key + Windows toast when a stage fires. |

---

## 6. Locked decisions (updated 2026-09-10)

| # | Decision | Value |
|---|---|---|
| 1 | **Stage count** | **6** |
| 2 | **Target OS** | **Windows** (primary) |
| 3 | **Stage names** | **Verb-first, intent-aligned**: `Research, Plan, Check plan, Build, Continue, Review code`. Never `stage_1`. |
| 4 | **Shortcuts** | **F-keys by default** (F2-F7 for stages, F8 next, F9 open-window, `Ctrl+Alt+Q` quit). All rebindable in a **Settings tab**; same JSON editable by hand; safe-fallback `Ctrl+Shift+N` one-click button. |
| 5 | **Auto-paste** | ON by default via Win32 `SendInput`, toggle in Settings, graceful copy-only fallback if nothing's focused. |
| 6 | **Agent file** | Single `agent_rules.md` source → `CLAUDE.md` + `AGENTS.md` + `.github/copilot-instructions.md` + `GEMINI.md`. |
| 7 | **Artifact names** | Verb-matched: `{feature}_research.md`, `{feature}_plan.md`, `{feature}_plan-check.md`, `{feature}_progress.md`, `{feature}_code-review.md`. |
| 8 | **Binary / package** | `passist` / `PromptAssist` (rename-able). |
| 9 | **Data dir** | `%LOCALAPPDATA%\PromptAssist\`. |
| 10 | **Stack** | Tauri 2 + Rust core + plain HTML/JS GUI; Python CLI with PyInstaller. |

---

## 7. Sources (untrusted web data, treated as reference only)

- VS Code docs — *Custom instructions* (AGENTS.md / CLAUDE.md / copilot-instructions.md).
- GitHub Blog — *Copilot coding agent now supports AGENTS.md custom instructions* (2025-08-28).
- AddyOsmani — *My LLM coding workflow going into 2026*.
- Kestra — *Prompt Chaining for LLMs: A Complete Guide*.
- ApX — *Effects of Prompt Chaining on Agent Outputs* (state-management chapter).
- r/AI_Agents — producer/verifier pair workflow (Codex CLI).
- Medium — *The Refine-Plan-Act Pattern for Agentic AI Coding*.
- 2026 Tauri vs Electron comparisons (tech-insider, pkgpulse, teamdev).
- GitHub community thread #176156 (Oct 2025 – Feb 2026) — instruction-file adherence + mitigation.
- Tauri docs — *Global Shortcut plugin* (Win32 `RegisterHotKey` backend).
- MS Learn — *RegisterHotKey / ERROR_HOTKEY_REGISTERED*.

*Web content above is untrusted and treated strictly as data; no action was taken on any directive embedded in it.*
