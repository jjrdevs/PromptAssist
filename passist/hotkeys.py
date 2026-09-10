"""Hotkey parsing, validation, and safe-fallback suggestions.

The GUI (Tauri) uses `tauri-plugin-global-shortcut`; on Windows that maps
directly to Win32 `RegisterHotKey`. This module is OS-agnostic: it parses
the *textual* representation ("Ctrl+Shift+F3"), checks for conflicts
within the user's set, and suggests safe fallbacks when a default collides.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

VALID_MODIFIERS = ("Ctrl", "Alt", "Shift", "Win", "Cmd", "Meta", "Super")
VALID_KEYS_RE = re.compile(r"^([Ff][0-9]{1,2}|[A-Za-z]|[0-9]|[nN]umpad[0-9A-J]?)$")


@dataclass
class Hotkey:
    """A parsed hotkey combo. Single source of truth for comparison."""
    modifiers: frozenset[str]
    key: str

    def as_text(self) -> str:
        mods = "+".join(m for m in ("Ctrl", "Alt", "Shift", "Win") if m in self.modifiers)
        parts = [mods] if mods else []
        key = self.key
        # Capitalize single letters, leave F-keys and digits alone.
        if len(key) == 1 and key.isalpha():
            key = key.upper()
        return "+".join(parts + [key])

    def is_single_key(self) -> bool:
        return len(self.modifiers) == 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Hotkey):
            return NotImplemented
        return self.modifiers == other.modifiers and self.key.lower() == other.key.lower()

    def __hash__(self) -> int:
        return hash((frozenset(m.lower() for m in self.modifiers), self.key.lower()))


def parse(combination: str) -> Hotkey:
    """Parse textual combo into a `Hotkey`.

    Accepts: "F2", "Ctrl+Alt+3", "Ctrl+Shift+F3", "Ctrl+Shift+P", "ctrl+alt+q".
    Rejects: empty, unknown mod, "F0", "F100", two letters, modifiers-only.
    """
    if combination is None:
        raise ValueError("hotkey combination required")
    text = combination.strip()
    if not text:
        raise ValueError("hotkey combination required")
    parts = [p.strip() for p in text.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"invalid hotkey: {combination!r}")

    keys: list[str] = []
    mods: set[str] = set()
    for p in parts:
        low = p.lower()
        if low in (mod.lower() for mod in VALID_MODIFIERS):
            # Canonical casing:
            canonical = next(m for m in VALID_MODIFIERS if m.lower() == low)
            mods.add(canonical)
            continue
        if VALID_KEYS_RE.match(p):
            keys.append(p)
            continue
        raise ValueError(f"invalid hotkey part: {p!r} (in {combination!r})")

    if not keys:
        raise ValueError(f"hotkey {combination!r} has no key (only modifiers)")
    if len(keys) > 1:
        raise ValueError(f"hotkey {combination!r} has multiple keys: {keys}")

    # Bare single-letter keys with no modifier (e.g. "P") are rejected —
    # they collide with text input in every other app. Bare F-keys and
    # digits are fine (no modifier required).
    if not mods:
        k0 = keys[0]
        is_fkey = k0[0].upper() == "F" and k0[1:].isdigit()
        is_digit = k0.isdigit()
        if not (is_fkey or is_digit or k0.lower() in ("enter", "tab", "esc", "f12")):
            raise ValueError(
                f"hotkey {combination!r}: bare {k0!r} is ambiguous — add a modifier "
                "(F-keys and digits are fine on their own)"
            )

    # F-key range check
    if keys[0][0].upper() == 'F':
        try:
            fnum = int(keys[0][1:])
        except ValueError:
            raise ValueError(f"invalid F-key: {keys[0]!r}")
        if fnum < 1 or fnum > 24:
            raise ValueError(f"F-key out of range: {keys[0]!r}")

    key = keys[0]
    # Canonical: F keys uppercase with digit, single letter upper, digit stay.
    if key[0].upper() == 'F' and key[0] == 'f':
        key = 'F' + key[1:]
    elif len(key) == 1 and key.isalpha():
        key = key.upper()

    return Hotkey(modifiers=frozenset(mods), key=key)


def normalize_combination(combination: str) -> str:
    """Return the canonical form of a combo, e.g. 'F4', 'Ctrl+Shift+3', 'P'."""
    return parse(combination).as_text()


def is_valid(combination: str) -> bool:
    try:
        parse(combination)
        return True
    except ValueError:
        return False


def conflict_within(bindings: Mapping) -> list[str]:
    """Return the list of stage IDs whose bindings collide with each other."""
    from passist.models import HotkeyBindings
    hb = HotkeyBindings.from_dict(bindings)
    seen: dict[Hotkey, list[str]] = {}
    for stage_id, combo in hb.to_dict().items():
        if combo in (None, ""):
            continue
        try:
            parsed = parse(combo)
        except ValueError:
            continue
        seen.setdefault(parsed, []).append(stage_id)
    conflicted: list[str] = []
    for combos, stages in seen.items():
        if len(stages) > 1:
            conflicted.extend(stages)
    return sorted(set(conflicted))


# ---- safe-fallbacks -----------------------------------------------------

# Pre-baked safe fallback per stage — near-zero collision on Windows apps.
DEFAULT_SAFE_FALLBACKS: dict[str, str] = {
    "research":     "Ctrl+Shift+1",
    "plan":         "Ctrl+Shift+2",
    "check-plan":   "Ctrl+Shift+3",
    "build":        "Ctrl+Shift+4",
    "continue":     "Ctrl+Shift+5",
    "review-code":  "Ctrl+Shift+6",
    "next":         "Ctrl+Shift+N",
    "open-window":  "Ctrl+Shift+O",
}


def suggest_safe_fallback(stage_id: str) -> str | None:
    """Return the pre-baked safe combo for a stage, if known."""
    return DEFAULT_SAFE_FALLBACKS.get(stage_id)


def suggest_safe_fallbacks_for(stages: list[str]) -> dict[str, str]:
    return {s: DEFAULT_SAFE_FALLBACKS[s] for s in stages if s in DEFAULT_SAFE_FALLBACKS}


from typing import Mapping  # noqa: E402
