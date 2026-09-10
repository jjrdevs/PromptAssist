"""CLI end-to-end tests — run the CLI in a subprocess."""
from __future__ import annotations

from pathlib import Path

from conftest import run_cli


class TestNew:
    def test_creates_feature(self, cli_env, target_repo: Path):
        r = run_cli(["new", "add session logging", "--target", str(target_repo)],
                    env=cli_env)
        assert r.returncode == 0, r.stderr
        assert "created" in r.stdout.lower()

    def test_requires_target(self, cli_env):
        r = run_cli(["new", "feat"], env=cli_env)
        assert r.returncode == 1
        assert "target" in r.stderr.lower()

    def test_normalizes_name(self, cli_env, target_repo: Path):
        r = run_cli(["new", "Add Session Logging!!", "--target", str(target_repo)],
                    env=cli_env)
        assert r.returncode == 0
        assert "add_session_logging" in r.stdout


class TestRun:
    def test_research(self, cli_env, target_repo: Path):
        run_cli(["new", "feat", "--target", str(target_repo)], env=cli_env)
        r = run_cli(["run", "research", "feat"], env=cli_env)
        assert r.returncode == 0, r.stderr
        assert r.stdout.startswith("[STAGE: RESEARCH")
        assert "feat_research.md" in r.stdout

    def test_all_six(self, cli_env, target_repo: Path):
        run_cli(["new", "feat", "--target", str(target_repo)], env=cli_env)
        for stage, header in [
            ("research", "[STAGE: RESEARCH"),
            ("plan",     "[STAGE: PLAN"),
            ("check-plan", "[STAGE: CHECK PLAN"),
            ("build",    "[STAGE: BUILD"),
            ("continue", "[STAGE: CONTINUE"),
            ("review-code", "[STAGE: REVIEW CODE"),
        ]:
            r = run_cli(["run", stage, "feat"], env=cli_env)
            assert r.returncode == 0, f"{stage}: {r.stderr}"
            assert r.stdout.startswith(header), f"{stage}: expected {header!r} got {r.stdout[:60]!r}"

    def test_unknown_stage_rejected(self, cli_env):
        r = run_cli(["run", "nonsense", "feat"], env=cli_env)
        assert r.returncode == 2
        assert "invalid choice" in r.stderr.lower()


class TestLs:
    def test_list_empty(self, cli_env):
        r = run_cli(["ls"], env=cli_env)
        assert r.returncode == 0
        assert "no features" in r.stdout.lower()

    def test_list_with(self, cli_env, target_repo: Path):
        run_cli(["new", "feat", "--target", str(target_repo)], env=cli_env)
        r = run_cli(["ls"], env=cli_env)
        assert "feat" in r.stdout
        assert str(target_repo) in r.stdout


class TestExport:
    def test_all_six_to_dir(self, cli_env, target_repo: Path):
        run_cli(["new", "feat", "--target", str(target_repo)], env=cli_env)
        out = target_repo / "prompts"
        r = run_cli(["export", "feat", "--out", str(out)], env=cli_env)
        assert r.returncode == 0
        files = sorted(p.name for p in out.glob("*.txt"))
        assert len(files) == 6, files
        # Content check
        research = (out / "feat_research.txt").read_text(encoding="utf-8")
        assert research.startswith("[STAGE: RESEARCH")
        assert "feat_research.md" in research

    def test_single_stage(self, cli_env, target_repo: Path):
        run_cli(["new", "feat", "--target", str(target_repo)], env=cli_env)
        out = target_repo / "one"
        r = run_cli(["export", "feat", "plan", "--out", str(out)], env=cli_env)
        assert r.returncode == 0
        files = list(out.glob("*.txt"))
        assert len(files) == 1
        assert files[0].name == "feat_plan.txt"


class TestSyncAgent:
    def test_all_four(self, cli_env, target_repo: Path):
        r = run_cli(["sync-agent", "--target", str(target_repo)], env=cli_env)
        assert r.returncode == 0, r.stderr
        for expected in ("CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md", "GEMINI.md"):
            assert (target_repo / expected).exists(), f"missing {expected}"

    def test_subset(self, cli_env, target_repo: Path):
        r = run_cli(["sync-agent", "--target", str(target_repo), "--tools", "CLAUDE.md,AGENTS.md"], env=cli_env)
        assert r.returncode == 0
        assert (target_repo / "CLAUDE.md").exists()
        assert (target_repo / "AGENTS.md").exists()
        assert not (target_repo / "GEMINI.md").exists()

    def test_invalid_target(self, cli_env):
        r = run_cli(["sync-agent", "--target", "/nonexistent/path"], env=cli_env)
        assert r.returncode in (1, 2)
        assert r.stderr


class TestBind:
    def test_bind_and_show(self, cli_env):
        r = run_cli(["bind", "research", "Ctrl+Shift+1"], env=cli_env)
        assert r.returncode == 0, r.stderr
        r2 = run_cli(["show"], env=cli_env)
        assert "Ctrl+Shift+1" in r2.stdout

    def test_bind_clear(self, cli_env):
        run_cli(["bind", "research", "F2"], env=cli_env)
        run_cli(["bind", "research", "--clear"], env=cli_env)
        import json as _json
        r = run_cli(["show"], env=cli_env)
        s = _json.loads(r.stdout)
        # cleared → null in JSON
        assert s["hotkeys"]["research"] is None or s["hotkeys"]["research"] == ""

    def test_invalid_combo_rejected(self, cli_env):
        r = run_cli(["bind", "research", "Ctrl+Shift"], env=cli_env)
        assert r.returncode != 0
        assert "no key" in r.stderr.lower() or "invalid" in r.stderr.lower() or "invalid hotkey" in r.stderr.lower()


class TestListBindings:
    def test_six_defaults(self, cli_env):
        r = run_cli(["list-bindings"], env=cli_env)
        assert r.returncode == 0
        for expected in ("research", "plan", "check-plan", "build", "continue", "review-code"):
            assert expected in r.stdout

    def test_safe_fallbacks_shown(self, cli_env):
        r = run_cli(["list-bindings"], env=cli_env)
        assert "Ctrl+Shift+1" in r.stdout
        assert "Ctrl+Shift+6" in r.stdout


class TestApplySafeFallbacks:
    def test_applies_all_six(self, cli_env):
        r = run_cli(["apply-safe-fallbacks"], env=cli_env)
        assert r.returncode == 0
        r2 = run_cli(["show"], env=cli_env)
        import json
        s = json.loads(r2.stdout)
        for stage in ("research", "plan", "check-plan", "build", "continue", "review-code"):
            assert s["hotkeys"][stage] in {"Ctrl+Shift+1","Ctrl+Shift+2","Ctrl+Shift+3","Ctrl+Shift+4","Ctrl+Shift+5","Ctrl+Shift+6"}


class TestReset:
    def test_reset_returns_to_shift_f_defaults(self, cli_env):
        run_cli(["apply-safe-fallbacks"], env=cli_env)
        run_cli(["reset"], env=cli_env)
        r = run_cli(["show"], env=cli_env)
        import json
        s = json.loads(r.stdout)
        assert s["hotkeys"]["research"] == "Shift+F2"
