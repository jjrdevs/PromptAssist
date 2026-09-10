"""Typed domain models for PromptAssist.

Deliberately simple — dataclasses, no ORM, no serialization framework.
Everything is JSON/YAML-serializable via the helper functions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, ClassVar, Mapping


#: The 6 stage IDs in execution order. Never `stage_#` — intent-aligned,
#: verb-first names. This is the single source of truth.
StageOrder: tuple[str, ...] = (
    "research",
    "plan",
    "check-plan",
    "build",
    "continue",
    "review-code",
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Stage:
    """One of the six workflow stages.

    `stop_rule` is a mandatory header the render function prepends to the
    body, so the agent never drifts across stage boundaries mid-session.
    """

    id: str                       # "research" | "plan" | ...
    name: str                     # "Research" (user-facing)
    stop_rule: str                # mandatory stage-boundary header
    prompt: str                   # the stage body (placeholders allowed)
    artifact: str                 # template filename, e.g. "{feature_name}_research.md"
    path: str                     # directory relative to target_repo, e.g. "docs/development"
    default_hotkey: str           # e.g. "F2"
    fallback_hotkey: str          # e.g. "Ctrl+Shift+1"

    def artifact_for(self, feature_name: str) -> str:
        """Render the artifact path for a given feature."""
        rel = self.artifact.format(feature_name=feature_name)
        # `path` comes from YAML; normalize separators.
        return f"{self.path.rstrip('/')}/{rel}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Feature:
    """A tracked feature with its target repo and progress markers."""

    name: str                                 # snake_case, normalized
    target_repo: str                          # absolute path to repo
    created: str                              # ISO-8601 UTC
    last_fired_stage: str | None = None       # most-recently fired stage id
    total_fires: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def new(name: str, target_repo: str) -> "Feature":
        return Feature(name=name, target_repo=target_repo, created=_iso_now())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Feature":
        return cls(
            name=d["name"],
            target_repo=d["target_repo"],
            created=d["created"],
            last_fired_stage=d.get("last_fired_stage"),
            total_fires=int(d.get("total_fires", 0)),
            extra=dict(d.get("extra", {})),
        )


@dataclass
class HotkeyBindings:
    """User's per-stage hotkey overrides.

    `value == ""`  →  user disabled the stage's hotkey (button only).
    `value is None` →  user has not overridden — use the stage's *default*.

    The CLI's `bind <stage> <combo>` writes here, and the Settings tab
    (in the Tauri GUI) does the same thing through the same JSON file.
    """

    research: str | None = None
    plan: str | None = None
    check_plan: str | None = None
    build: str | None = None
    continue_: str | None = None
    review_code: str | None = None
    next_: str | None = None
    open_window: str | None = None
    quit_: str | None = None

    # YAML/JSON keys use stage ids (with hyphens), not Python underscored
    # dataclass names.
    KEY_TO_FIELD: ClassVar[dict[str, str]] = {
        "research": "research",
        "plan": "plan",
        "check-plan": "check_plan",
        "build": "build",
        "continue": "continue_",
        "review-code": "review_code",
        "next": "next_",
        "open-window": "open_window",
        "quit": "quit_",
    }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any] | None) -> "HotkeyBindings":
        d = d or {}
        inst = cls()
        for key, field_name in cls.KEY_TO_FIELD.items():
            if key in d:
                raw = d[key]
                # Empty string is explicit "disabled" (button only).
                # None is "use the stage default".
                setattr(inst, field_name, ("" if raw in (None, "") else str(raw)) if raw is not None else None)
        return inst

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, field_name in self.KEY_TO_FIELD.items():
            v = getattr(self, field_name, None)
            if v is None:
                # Preserve the None → default sentinel (omit in JSON is fine).
                out[key] = None
            else:
                out[key] = v
        return out
