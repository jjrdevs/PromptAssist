"""Simple desktop launcher for PromptAssist.

This keeps the stage buttons and adds a dedicated settings tab for hotkeys,
while still delegating the real prompt rendering to the installed ``passist``
CLI. On Windows it also listens for the configured global hotkeys and auto-pastes
into the foreground app when enabled.

Usage:
    python passist_gui_launcher.py --dry-run research my_feature
    passist_gui_launcher.exe
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

from passist.hotkeys import normalize_combination
from passist.storage import load_settings, save_settings

try:
    import keyboard  # type: ignore
except Exception:  # pragma: no cover - environment optional
    keyboard = None

STAGES = [
    ("research", "Research"),
    ("plan", "Plan"),
    ("check-plan", "Check plan"),
    ("build", "Build"),
    ("continue", "Continue"),
    ("review-code", "Review code"),
]

HOTKEY_ROWS = [
    ("research", "Research"),
    ("plan", "Plan"),
    ("check-plan", "Check plan"),
    ("build", "Build"),
    ("continue", "Continue"),
    ("review-code", "Review code"),
    ("next", "Next stage"),
    ("open-window", "Open window"),
    ("quit", "Quit"),
]


def _resolve_passist_executable() -> Path:
    root = Path(__file__).resolve().parent
    candidates = [
        root / "dist" / "passist.exe",
        root / "passist.exe",
        root / ".venv" / "Scripts" / "passist.exe",
        Path.cwd() / "dist" / "passist.exe",
        Path.cwd() / "passist.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    for name in ("passist.exe", "passist"):
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved)

    return Path("passist.exe")


def _hidden_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        startupinfo=startupinfo,
        creationflags=creationflags,
        **kwargs,
    )


def _run_passist(*args: str) -> dict:
    exe = _resolve_passist_executable()
    command = [str(exe), "--json", *args]
    result = _hidden_run(command)
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "PromptAssist failed").strip()
        raise RuntimeError(details)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from passist: {exc}") from exc


def _build_dry_run_command(stage: str | None, feature: str | None) -> str:
    exe = _resolve_passist_executable()
    command = [str(exe)]
    if stage:
        command.extend(["run", stage])
    if feature:
        command.append(feature)
    return " ".join(command)


def _load_hotkeys() -> dict[str, str]:
    payload = _run_passist("list-bindings")
    bindings = payload.get("bindings") or []
    out: dict[str, str] = {}
    for entry in bindings:
        stage = str(entry.get("stage") or "").strip()
        value = (entry.get("effective") or "").strip()
        if stage and value and value != "—":
            out[stage] = value
    return out


def _save_hotkey(stage: str, value: str) -> None:
    _save_hotkeys_batch({stage: value})


def _save_hotkeys_batch(updates: dict[str, str]) -> None:
    settings = load_settings()
    hotkeys = dict(settings.get("hotkeys") or {})
    for stage, value in updates.items():
        cleaned = (value or "").strip()
        if not cleaned:
            hotkeys[stage] = ""
        else:
            hotkeys[stage] = normalize_combination(cleaned)
    settings["hotkeys"] = hotkeys
    save_settings(settings)


def _keyboard_combo(value: str) -> str:
    text = (value or "").strip().lower().replace(" ", "")
    return text.replace("ctrl+", "ctrl+").replace("alt+", "alt+").replace("shift+", "shift+")


def _send_paste_event() -> None:
    if os.name != "nt":
        return
    try:
        user32 = ctypes.windll.user32
        user32.keybd_event(0x11, 0, 0, 0)  # Ctrl
        time.sleep(0.05)
        user32.keybd_event(0x56, 0, 0, 0)  # V
        time.sleep(0.05)
        user32.keybd_event(0x56, 0, 0x0002, 0)
        user32.keybd_event(0x11, 0, 0x0002, 0)
        return
    except Exception:
        pass
    if keyboard is not None:
        try:
            keyboard.press_and_release("ctrl+v")
        except Exception:
            pass


class PromptAssistApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PromptAssist")
        self.geometry("980x680")
        self.minsize(820, 520)

        self.feature_var = tk.StringVar(value="my_feature")
        self.repo_var = tk.StringVar(value=r"C:\path\to\repo")
        self.status_var = tk.StringVar(value="Ready")
        self.auto_paste_var = tk.BooleanVar(value=True)
        self.hotkey_hooks: dict[str, str] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 0))

        self.stages_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.stages_tab, text="Stages")
        self.notebook.add(self.settings_tab, text="Settings")

        self._build_stages_tab()
        self._build_settings_tab()

        self._install_global_hotkeys()

        status = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _build_stages_tab(self) -> None:
        stage_frame = ttk.LabelFrame(self.stages_tab, text="Stages", padding=(12, 10))
        stage_frame.grid(row=0, column=0, sticky="nsew", padx=(12, 12), pady=(12, 8))
        stage_frame.columnconfigure((0, 1, 2), weight=1)

        top = ttk.Frame(self.stages_tab, padding=(12, 12, 12, 8))
        top.grid(row=1, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Feature:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(top, textvariable=self.feature_var).grid(row=0, column=1, sticky="ew")

        ttk.Label(top, text="Target repo:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Entry(top, textvariable=self.repo_var).grid(row=1, column=1, sticky="ew", pady=(8, 0))

        buttons = ttk.Frame(top)
        buttons.grid(row=0, column=2, rowspan=2, sticky="e", padx=(12, 0))
        ttk.Button(buttons, text="New feature", command=self.create_feature).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Copy output", command=self.copy_output).pack(side=tk.LEFT)

        self.stage_buttons: dict[str, ttk.Button] = {}
        for idx, (stage_id, label) in enumerate(STAGES):
            btn = ttk.Button(stage_frame, text=label, command=lambda sid=stage_id: self.fire_stage(sid))
            row = idx // 3
            col = idx % 3
            btn.grid(row=row, column=col, sticky="ew", padx=6, pady=6)
            self.stage_buttons[stage_id] = btn

        output_frame = ttk.LabelFrame(self.stages_tab, text="Rendered prompt", padding=(12, 10))
        output_frame.grid(row=2, column=0, sticky="nsew", padx=(12, 12), pady=(0, 12))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.output = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.output.grid(row=0, column=0, sticky="nsew")

    def _build_settings_tab(self) -> None:
        settings_frame = ttk.LabelFrame(self.settings_tab, text="Settings", padding=(12, 10))
        settings_frame.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        settings_frame.columnconfigure(1, weight=1)

        ttk.Checkbutton(settings_frame, text="Auto-paste into the active app", variable=self.auto_paste_var).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        self.hotkey_vars: dict[str, tk.StringVar] = {}
        for idx, (stage_id, label) in enumerate(HOTKEY_ROWS, start=1):
            ttk.Label(settings_frame, text=label).grid(row=idx, column=0, sticky="w", padx=(0, 8), pady=4)
            entry = ttk.Entry(settings_frame, width=24)
            entry.grid(row=idx, column=1, sticky="ew", padx=(0, 8), pady=4)
            self.hotkey_vars[stage_id] = tk.StringVar()
            entry.config(textvariable=self.hotkey_vars[stage_id])

        actions = ttk.Frame(settings_frame)
        actions.grid(row=len(HOTKEY_ROWS) + 1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="Save hotkeys", command=self.save_hotkeys).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Use safe fallbacks", command=self.apply_safe_fallbacks).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Reset defaults", command=self.reset_hotkeys).pack(side=tk.LEFT)

        self.refresh_hotkeys()

    def _feature_name(self) -> str:
        name = self.feature_var.get().strip()
        if not name:
            raise ValueError("Please enter a feature name.")
        return name

    def _paste_active_window(self) -> None:
        if not self.auto_paste_var.get():
            return
        time.sleep(0.08)
        _send_paste_event()

    def _on_stage_trigger(self, stage: str) -> None:
        feature = self._feature_name()
        try:
            payload = _run_passist("run", stage, feature)
            text = payload.get("text") or ""
            self.output.delete("1.0", tk.END)
            self.output.insert(tk.END, text)
            self.output.see(tk.END)
            self.status_var.set(f"Rendered {payload.get('stage_name', stage)} for {feature}")
            self.clipboard_clear(); self.clipboard_append(text)
            self._paste_active_window()
        except Exception as exc:  # pragma: no cover - UI path only
            self.status_var.set(f"Error: {exc}")

    def create_feature(self) -> None:
        feature = self._feature_name()
        repo = self.repo_var.get().strip()
        if not repo:
            messagebox.showerror("PromptAssist", "Please enter a target repo path.")
            return
        try:
            payload = _run_passist("new", feature, "--target", repo)
            self.status_var.set(f"Created feature '{payload.get('name', feature)}'")
            self.output.delete("1.0", tk.END)
            self.output.insert(tk.END, json.dumps(payload, indent=2))
        except Exception as exc:  # pragma: no cover - UI path only
            messagebox.showerror("PromptAssist", str(exc))

    def fire_stage(self, stage: str) -> None:
        self._on_stage_trigger(stage)

    def copy_output(self) -> None:
        text = self.output.get("1.0", tk.END).rstrip("\n")
        if not text:
            messagebox.showinfo("PromptAssist", "There is no prompt to copy yet.")
            return
        self.clipboard_clear(); self.clipboard_append(text)
        self.status_var.set("Prompt copied to clipboard")

    def refresh_hotkeys(self) -> None:
        try:
            binds = _load_hotkeys()
        except Exception as exc:  # pragma: no cover - UI path only
            self.status_var.set(f"Hotkeys unavailable: {exc}")
            return
        for stage_id, _label in HOTKEY_ROWS:
            self.hotkey_vars[stage_id].set(binds.get(stage_id, ""))
        self.status_var.set("Hotkeys loaded")

    def save_hotkeys(self) -> None:
        try:
            updates: dict[str, str] = {}
            for stage_id, _label in HOTKEY_ROWS:
                updates[stage_id] = self.hotkey_vars[stage_id].get().strip()
            _save_hotkeys_batch(updates)
            self.status_var.set("Hotkeys saved")
            self.refresh_hotkeys()
            self._install_global_hotkeys()
        except Exception as exc:  # pragma: no cover - UI path only
            messagebox.showerror("PromptAssist", str(exc))

    def apply_safe_fallbacks(self) -> None:
        try:
            result = _hidden_run([str(_resolve_passist_executable()), "apply-safe-fallbacks"])
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Could not apply safe fallbacks")
            self.status_var.set("Safe fallbacks applied")
            self.refresh_hotkeys()
            self._install_global_hotkeys()
        except Exception as exc:  # pragma: no cover - UI path only
            messagebox.showerror("PromptAssist", str(exc))

    def reset_hotkeys(self) -> None:
        try:
            result = _hidden_run([str(_resolve_passist_executable()), "reset"])
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Could not reset hotkeys")
            self.status_var.set("Hotkeys reset to defaults")
            self.refresh_hotkeys()
            self._install_global_hotkeys()
        except Exception as exc:  # pragma: no cover - UI path only
            messagebox.showerror("PromptAssist", str(exc))

    def _install_global_hotkeys(self) -> None:
        if keyboard is None:
            self.status_var.set("keyboard package not installed; global hotkeys are disabled")
            return
        try:
            for hotkey_name in list(self.hotkey_hooks.keys()):
                try:
                    keyboard.remove_hotkey(hotkey_name)
                except Exception:
                    pass
            self.hotkey_hooks.clear()

            binds = _load_hotkeys()
            for stage_id, label in HOTKEY_ROWS:
                combo = binds.get(stage_id, "")
                if not combo:
                    continue
                combo_key = _keyboard_combo(combo)
                if not combo_key:
                    continue
                self.hotkey_hooks[combo_key] = stage_id
                keyboard.add_hotkey(combo_key, lambda sid=stage_id: self._on_stage_trigger(sid), suppress=False)
            self.status_var.set("Global hotkeys installed")
        except Exception as exc:  # pragma: no cover - UI path only
            self.status_var.set(f"Hotkey error: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="PromptAssist desktop launcher")
    parser.add_argument("stage", nargs="?", help="Optional stage to render immediately")
    parser.add_argument("feature", nargs="?", help="Optional feature to use")
    parser.add_argument("--dry-run", action="store_true", help="Print the command without launching the GUI")
    args = parser.parse_args()

    if args.dry_run:
        print(_build_dry_run_command(args.stage, args.feature))
        return 0

    if args.stage and args.feature:
        app = PromptAssistApp()
        app.feature_var.set(args.feature)
        app.after(100, lambda: app.fire_stage(args.stage))
        app.mainloop()
        return 0

    app = PromptAssistApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
