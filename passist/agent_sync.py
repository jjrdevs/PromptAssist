"""Write `agent_rules.md` into per-tool agent files inside the target repo.

- `CLAUDE.md` — Claude Code
- `AGENTS.md` — Codex CLI and VS Code custom instructions
- `.github/copilot-instructions.md` — Copilot
- `GEMINI.md` — Gemini CLI

All four are byte-identical body, one-line tool-specific header.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from passist.storage import load_agent_rules


TOOL_HEADERS: dict[str, str] = {
    "CLAUDE.md":                  "## Project instructions (managed by PromptAssist)\n",
    "AGENTS.md":                  "## Project instructions (managed by PromptAssist)\n",
    ".github/copilot-instructions.md": "## Project instructions (managed by PromptAssist)\n",
    "GEMINI.md":                  "## Project instructions (managed by PromptAssist)\n",
}

ALL_TARGETS: tuple[str, ...] = tuple(TOOL_HEADERS.keys())


def render_for_tool(tool: str) -> str:
    """Return the full file content for `tool` (header + body).

    The body is the user's `agent_rules.md` verbatim. We do not substitute
    anything — the prompt's `{feature_name}` is filled in by the *prompt*,
    not the agent file. The agent file is static.
    """
    if tool not in TOOL_HEADERS:
        raise KeyError(f"unknown tool: {tool!r}")
    body = load_agent_rules()
    return f"{TOOL_HEADERS[tool]}\n{body.lstrip()}\n"


def sync_agent(target_repo: str, tools: Sequence[str] | None = None,
               create_dirs: bool = True) -> list[Path]:
    """Write all (or a subset of) agent files inside `target_repo`.

    Returns the list of paths written.
    """
    repo = Path(target_repo).expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(f"target repo does not exist: {repo}")

    tools = list(tools) if tools else list(ALL_TARGETS)
    written: list[Path] = []
    for tool in tools:
        dest = repo / tool
        if create_dirs:
            dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render_for_tool(tool), encoding="utf-8")
        written.append(dest)
    return written


# `sync_agent_into_repo` alias for readability.
sync_agent_into_repo = sync_agent

