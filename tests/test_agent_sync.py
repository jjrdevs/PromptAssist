"""Agent-file sync tests — the render-for-tool + write-to-repo loop."""
from __future__ import annotations

from pathlib import Path

from passist.agent_sync import ALL_TARGETS, render_for_tool, sync_agent
from passist.storage import load_agent_rules


class TestRenderForTool:
    def test_known_tools(self):
        for t in ("CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md", "GEMINI.md"):
            out = render_for_tool(t)
            assert "Project AI Development Instructions" in out
            assert "managed by PromptAssist" in out

    def test_unknown(self):
        import pytest
        with pytest.raises(KeyError):
            render_for_tool("UNKNOWN_TOOL.md")


class TestSyncAgent:
    def test_writes_all(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hi')")
        written = sync_agent(str(tmp_path))
        assert len(written) == 4
        for expected in ("CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md", "GEMINI.md"):
            assert (tmp_path / expected).exists()

    def test_creates_github_dir(self, tmp_path: Path):
        sync_agent(str(tmp_path))
        assert (tmp_path / ".github" / "copilot-instructions.md").exists()

    def test_no_mkdirs_mode(self, tmp_path: Path):
        # Pre-create the .github dir but NOT CLAUDE.md's parent (it's root, so this won't fail).
        (tmp_path / ".github").mkdir()
        # With --no-mkdirs, we should still not raise for existing files.
        try:
            import passist.agent_sync as ag
            ag.sync_agent(str(tmp_path), tools=[".github/copilot-instructions.md"], create_dirs=False)
        except Exception as e:
            raise AssertionError(f"unexpected: {e}")


class TestAgentRulesContent:
    def test_has_all_seven_sections(self):
        body = load_agent_rules()
        for heading in (
            "General Development Rules",
            "Documentation Rules",
            "Planning Rules",
            "Implementation Rules",
            "Progress Tracking",
            "Architecture Decisions",
            "Completion Verification",
        ):
            assert heading in body, f"missing section: {heading}"

    def test_feature_name_placeholder(self):
        body = load_agent_rules()
        assert "{feature_name}" in body

    def test_docs_paths_use_forward_slash(self):
        body = load_agent_rules()
        # No Windows backslash paths left behind.
        assert "\\docs\\" not in body
        assert "docs/development" in body
