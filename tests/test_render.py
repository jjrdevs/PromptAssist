"""Render-core tests — the one function everything depends on."""
from __future__ import annotations

import pytest

from passist.render import (
    build_mapping,
    normalize_feature_name,
    render_all,
    render_stage,
    substitute,
)
from passist.storage import load_prompts, load_stages


def _stage(stage_id: str):
    return next(s for s in load_stages() if s.id == stage_id)


class TestNormalize:
    def test_basic(self):
        assert normalize_feature_name("add_session_logging") == "add_session_logging"

    def test_spaces(self):
        assert normalize_feature_name("add session logging") == "add_session_logging"

    def test_mixed_case(self):
        assert normalize_feature_name("AddSessionLogging") == "addsessionlogging"

    def test_with_slash(self):
        assert normalize_feature_name("features/add-session-logging") == "features_add_session_logging"

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            normalize_feature_name("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValueError):
            normalize_feature_name("   ")

    def test_long_rejected(self):
        with pytest.raises(ValueError):
            normalize_feature_name("x" * 200)


class TestSubstitute:
    def test_basic(self):
        out = substitute("Feature: {feature_name}", {"feature_name": "x"})
        assert out == "Feature: x"

    def test_unknown_leaves_as_is(self):
        out = substitute("{feature_name} and {unknown}", {"feature_name": "x"})
        assert out == "x and {unknown}"

    def test_underscore_names(self):
        out = substitute("{feature_name}", {"feature_name": "add_session_logging"})
        assert out == "add_session_logging"


class TestRenderStage:
    def test_feature_name_substituted(self):
        stage = _stage("research")
        out = render_stage(stage, "add session logging", "/tmp/repo")
        assert "add_session_logging" in out
        assert "[INSERT FEATURE]" not in out

    def test_stop_rule_present(self):
        stage = _stage("research")
        out = render_stage(stage, "x", "/tmp/repo")
        assert out.startswith("[STAGE: RESEARCH")

    def test_paths_filled(self):
        stage = _stage("plan")
        out = render_stage(stage, "feat", "/data/repo")
        assert "/data/repo" in out
        assert "docs/development/feat_research.md" in out

    def test_agent_name_overridable(self):
        stage = _stage("research")
        out_default = render_stage(stage, "x", "/tmp/repo")
        out_override = render_stage(stage, "x", "/tmp/repo", agent_name="Claude Code")
        # The agent name is in the *body* if the template references it.
        # The default template does not reference agent_name — so both should be equal.
        assert out_default == out_override

    def test_each_stage_stops_at_its_boundary(self):
        for stage_id in ("research", "plan", "check-plan", "build", "continue", "review-code"):
            stage = _stage(stage_id)
            out = render_stage(stage, "x", "/tmp")
            # Every stage must have a STAGE header (the boundary contract).
            assert "[STAGE" in out, f"{stage_id} missing stop-rule"

    def test_each_stage_has_different_name(self):
        names = [s.name for s in load_stages()]
        assert len(set(names)) == len(names) == 6

    def test_no_stage_number_leak(self):
        # Make sure user-facing names don't carry stage_number (intent rule).
        for s in load_stages():
            assert s.name
            assert not s.name.startswith("stage")


class TestRenderAll:
    def test_all_six(self):
        rendered = render_all("add_session_logging", "/tmp/repo")
        assert set(rendered.keys()) == {
            "research", "plan", "check-plan", "build", "continue", "review-code"
        }
        for body in rendered.values():
            assert "add_session_logging" in body


class TestStageArtifact:
    def test_artifact_path(self):
        stage = _stage("research")
        assert stage.artifact_for("feat") == "docs/development/feat_research.md"
