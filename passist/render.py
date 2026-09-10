"""Core prompt rendering.

One render function shared by CLI, GUI, and unit tests. All substitutions
happen here; every other consumer calls `render_stage` / `render_all`.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from passist.models import Stage, StageOrder

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def normalize_feature_name(name: str) -> str:
    """Normalize an arbitrary feature label to snake_case.

    - Strips.
    - Lowercases.
    - Replaces runs of non-alphanumeric with a single underscore.
    - Strips leading/trailing underscores.
    - Falls back to the original name if the result is empty.
    """
    raw = (name or "").strip()
    if not raw:
        raise ValueError("feature name must not be empty")
    lower = raw.lower()
    lower = re.sub(r"[_\s/]+", "_", lower)
    lower = re.sub(r"[^a-z0-9_]+", "_", lower)
    lower = re.sub(r"_+", "_", lower).strip("_")
    if not lower:
        # Fallback: keep the original (sanitized) for names that were all-unicode.
        lower = re.sub(r"[^a-z0-9_]+", "", lower) or "feature"
    if len(lower) > 80:
        raise ValueError(f"feature name too long (max 80 chars, got {len(lower)})")
    return lower


def substitute(template: str, mapping: Mapping[str, Any]) -> str:
    """Substitute `{name}` placeholders in `template`.

    Unknown placeholders are left as-is (so prompts can carry other
    placeholders like `{agent_name}` in the future without breakage).
    """
    def _replace(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in mapping:
            value = mapping[key]
            if value is None:
                return m.group(0)
            return str(value)
        return m.group(0)

    return _PLACEHOLDER_RE.sub(_replace, template)


def build_mapping(feature_name: str, target_repo: str, agent_name: str | None = None) -> dict[str, str]:
    """The standard substitution map used by all prompts.

    If `agent_name` is None, `{agent_name}` is left for the user's own
    agent file to fill (or the prompt leaves it as-is).
    """
    m: dict[str, str] = {
        "feature_name": feature_name,
        "target_repo": target_repo,
    }
    if agent_name is not None:
        m["agent_name"] = str(agent_name)
    return m


def render_stage(stage: Stage, feature_name: str, target_repo: str, agent_name: str | None = None) -> str:
    """Render one stage: `stop_rule` + blank line + `prompt`, then substitute.

    This is the single choke-point — the CLI, the Tauri GUI, and every
    unit test all call this. The result is what lands on the clipboard.
    """
    name = normalize_feature_name(feature_name)
    mapping = build_mapping(name, target_repo, agent_name)

    # The stop-rule references `stage N/6` — compute the position so we can
    # substitute `{stage_number}` if the template uses it.
    try:
        mapping["stage_number"] = StageOrder.index(stage.id) + 1
    except ValueError:
        pass

    header = stage.stop_rule or ""
    body = stage.prompt or ""
    combined = f"{header.rstrip()}\n\n{body.lstrip()}" if header else body

    return substitute(combined, mapping).strip() + "\n"


def render_all(feature_name: str, target_repo: str, agent_name: str | None = None,
               stages: Sequence | None = None) -> dict[str, str]:
    """Render all 6 stages. Returns `{stage_id: rendered_text}`."""
    from passist.storage import load_stages  # local import to avoid cycle
    loaded = stages or load_stages()
    out: dict[str, str] = {}
    for stage in loaded:
        out[stage.id] = render_stage(stage, feature_name, target_repo, agent_name)
    return out
