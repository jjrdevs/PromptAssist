from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from passist.storage import default_config

import passist_gui_launcher

ROOT = Path(__file__).resolve().parents[1]


def test_gui_launcher_dry_run_renders_command() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "passist_gui_launcher.py"), "--dry-run", "research", "my_feature"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    stdout = result.stdout.strip()
    assert "research" in stdout
    assert "my_feature" in stdout
    assert "passist" in stdout.lower()


def test_default_hotkeys_use_shift_f_keys() -> None:
    cfg = default_config()
    for stage, hotkey in {
        "research": "Shift+F2",
        "plan": "Shift+F3",
        "check-plan": "Shift+F4",
        "build": "Shift+F5",
        "continue": "Shift+F6",
        "review-code": "Shift+F7",
    }.items():
        assert cfg["hotkeys"][stage] == hotkey


def test_launcher_batch_save_uses_single_update(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(passist_gui_launcher, "_resolve_passist_executable", lambda: Path("passist.exe"))
    monkeypatch.setattr(passist_gui_launcher, "_hidden_run", lambda command, **kwargs: calls.append(command) or subprocess.CompletedProcess(command, 0, "", ""))

    passist_gui_launcher._save_hotkeys_batch({
        "research": "Shift+F2",
        "plan": "Shift+F3",
    })

    assert calls == []
