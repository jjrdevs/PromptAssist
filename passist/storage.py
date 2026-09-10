"""File storage & config.

Layout (under `DATA_DIR` — `%LOCALAPPDATA%\\PromptAssist` on Windows, `~/.config/promptassist`
on Linux/macOS, or `PROMPTASSIST_DATA_DIR` if set):

    DATA_DIR/
      settings.json          — user's hotkey overrides + app settings
      features.json          — registered features list
    (bundle, read-only at runtime):
      passist/data/prompts.yaml — 6 stage templates + defaults
      passist/data/agent_rules.md — single-source agent rules
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from passist.models import Feature, HotkeyBindings, Stage, StageOrder

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def data_dir() -> Path:
    """Where PromptAssist keeps user state (settings.json, features.json)."""
    override = os.environ.get("PROMPTASSIST_DATA_DIR")
    if override:
        p = Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p
    system = os.environ.get("LOCALAPPDATA")
    if system:
        p = Path(system) / "PromptAssist"
    else:
        p = Path.home() / ".config" / "promptassist"
    p.mkdir(parents=True, exist_ok=True)
    return p


def assets_dir() -> Path:
    """Where the bundled read-only data (prompts.yaml, agent_rules.md) lives.

    At runtime from a PyInstaller bundle this is next to the exe; when
    running from source, it's `passist/data`.
    """
    # 1) Env override (used in tests).
    env = os.environ.get("PROMPTASSIST_ASSETS_DIR")
    if env:
        return Path(env)

    # 2) PyInstaller: sys._MEIPASS points to the bundled assets dir.
    try:
        import sys
        if getattr(sys, "_MEIPASS", None):
            p = Path(sys._MEIPASS) / "passist" / "data"
            if p.exists():
                return p
    except Exception:
        pass

    # 3) Source tree: passist/data relative to this file.
    src = Path(__file__).resolve().parent / "data"
    return src


# ---------------------------------------------------------------------------
# YAML prompts
# ---------------------------------------------------------------------------

_PROMPT_DEFAULTS: dict[str, Any] = {
    "agent_name": "Copilot",
}

def load_prompts() -> dict[str, Any]:
    """Load `prompts.yaml`, apply defaults."""
    path = assets_dir() / "prompts.yaml"
    if not path.exists():
        raise FileNotFoundError(f"bundled prompts.yaml not found at {path}")
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    if "defaults" not in data:
        data["defaults"] = {}
    for k, v in _PROMPT_DEFAULTS.items():
        data["defaults"].setdefault(k, v)
    data.setdefault("stages", {})
    return data


def load_stages() -> list[Stage]:
    """Return stages in StageOrder (6 of them, or whatever the YAML defines).

    Order: prefer the order in `StageOrder`; if the YAML defines extra
    ids not in the list, append them in the YAML order.
    """
    data = load_prompts()
    raw_stages: dict[str, Any] = data.get("stages", {})

    by_id: dict[str, Any] = {}
    for k, v in raw_stages.items():
        if not isinstance(v, dict):
            continue
        by_id[k] = v
    ordered_keys = [k for k in StageOrder if k in by_id]
    ordered_keys += [k for k in by_id if k not in StageOrder]

    stages: list[Stage] = []
    for k in ordered_keys:
        v = by_id[k]
        stages.append(Stage(
            id=k,
            name=str(v.get("name") or k),
            stop_rule=str(v.get("stop_rule") or "").rstrip() + "\n" if v.get("stop_rule") else "",
            prompt=str(v.get("prompt") or "").rstrip() + "\n" if v.get("prompt") else "",
            artifact=str(v.get("artifact") or "{feature_name}_{id}.md"),
            path=str(v.get("path") or "docs/development"),
            default_hotkey=str(v.get("default_hotkey") or ""),
            fallback_hotkey=str(v.get("fallback_hotkey") or ""),
        ))
    return stages


def load_agent_rules() -> str:
    path = assets_dir() / "agent_rules.md"
    if not path.exists():
        raise FileNotFoundError(f"bundled agent_rules.md not found at {path}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# settings.json
# ---------------------------------------------------------------------------

def default_hotkey_overrides() -> dict[str, Any]:
    """The default per-stage hotkeys (F-keys), from the stage list."""
    out: dict[str, Any] = {}
    for stage in load_stages():
        # Map stage_id to the settings key (drop hyphen).
        out[stage.id] = stage.default_hotkey or None
    out["next"] = None            # F8 is not bound to a stage; leave None → use "F8"
    out["open-window"] = None
    out["quit"] = "Ctrl+Alt+Q"
    return out


def default_config() -> dict[str, Any]:
    """A fresh `settings.json` payload."""
    return {
        "version": 1,
        "auto_paste": True,
        "start_with_windows": False,
        "on_conflict": "fail_soft",
        "hotkeys": default_hotkey_overrides(),
    }


def settings_path() -> Path:
    return data_dir() / "settings.json"


def load_settings() -> dict[str, Any]:
    """Load `settings.json`, falling back to defaults.

    The *effective* hotkeys = the default set (from stages) merged with the
    user's overrides in settings.json. An empty string in settings.json means
    "user disabled this stage's hotkey" (button only).
    """
    p = settings_path()
    user: dict[str, Any] = {}
    if p.exists():
        try:
            user = json.loads(p.read_text(encoding="utf-8")) or {}
        except Exception:
            user = {}
    base = default_config()
    # Deep-merge user into base.
    merged = {**base, **user}
    merged["hotkeys"] = {**(base.get("hotkeys") or {}), **(user.get("hotkeys") or {})}
    return merged


def save_settings(payload: Mapping[str, Any]) -> Path:
    """Write `settings.json` atomically, validating the hotkeys."""
    from passist.hotkeys import parse, conflict_within
    hk = dict(payload.get("hotkeys") or {})
    # Validate everything.
    for k, v in hk.items():
        if v in (None, ""):
            continue
        parse(str(v))
    p = settings_path()
    tmp = p.with_suffix(".json.tmp")
    payload_out = dict(payload)
    payload_out["version"] = 1
    tmp.write_text(json.dumps(payload_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


# ---------------------------------------------------------------------------
# features.json
# ---------------------------------------------------------------------------

def features_path() -> Path:
    return data_dir() / "features.json"


def load_features() -> list[Feature]:
    p = features_path()
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [Feature.from_dict(item) for item in raw]


def save_features(features: list[Feature]) -> Path:
    p = features_path()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps([f.to_dict() for f in features], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


def get_feature(name: str) -> Feature | None:
    for f in load_features():
        if f.name == name:
            return f
    return None


def upsert_feature(f: Feature) -> None:
    feats = load_features()
    for i, existing in enumerate(feats):
        if existing.name == f.name:
            feats[i] = f
            break
    else:
        feats.append(f)
    save_features(feats)


def delete_feature(name: str) -> bool:
    feats = load_features()
    kept = [f for f in feats if f.name != name]
    if len(kept) == len(feats):
        return False
    save_features(kept)
    return True


def mark_fired(name: str, stage_id: str) -> Feature:
    """Mark the feature as having fired `stage_id`. Advances last_fired_stage."""
    f = get_feature(name)
    if f is None:
        raise LookupError(f"feature not found: {name!r}")
    f.last_fired_stage = stage_id
    f.total_fires = int(f.total_fires or 0) + 1
    upsert_feature(f)
    return f


def active_feature() -> Feature | None:
    """The most-recently-touched feature, or None if list is empty."""
    feats = load_features()
    if not feats:
        return None
    # Sort by created desc (features.json is a list, not a dict).
    return feats[-1]

