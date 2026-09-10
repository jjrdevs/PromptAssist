"""Settings + features round-trip tests."""
from __future__ import annotations

import json
from pathlib import Path

from passist.models import Feature
from passist.storage import (
    data_dir,
    default_config,
    get_feature,
    load_features,
    load_settings,
    mark_fired,
    save_features,
    save_settings,
    upsert_feature,
)


class TestDataDir:
    def test_env_override(self, data_dir):
        import passist.storage as st
        assert st.data_dir() == Path(data_dir)

    def test_default_created(self, data_dir):
        import passist.storage as st
        d = st.data_dir()
        assert d.exists()


class TestDefaultConfig:
    def test_six_stage_defaults(self):
        cfg = default_config()
        hk = cfg["hotkeys"]
        assert hk["research"] == "F2"
        assert hk["plan"] == "F3"
        assert hk["check-plan"] == "F4"
        assert hk["build"] == "F5"
        assert hk["continue"] == "F6"
        assert hk["review-code"] == "F7"

    def test_quit_default(self):
        cfg = default_config()
        assert cfg["hotkeys"]["quit"] == "Ctrl+Alt+Q"

    def test_auto_paste_default_on(self):
        assert default_config()["auto_paste"] is True

    def test_on_conflict_default_soft(self):
        assert default_config()["on_conflict"] == "fail_soft"


class TestSettingsRoundtrip:
    def test_load_returns_defaults_when_missing(self):
        s = load_settings()
        assert s["hotkeys"]["research"] == "F2"

    def test_bind_roundtrip(self):
        s = default_config()
        s["hotkeys"]["check-plan"] = "Ctrl+Shift+P"
        save_settings(s)
        s2 = load_settings()
        assert s2["hotkeys"]["check-plan"] == "Ctrl+Shift+P"
        # Other defaults preserved.
        assert s2["hotkeys"]["research"] == "F2"

    def test_disabled_stage_empty_string(self):
        s = default_config()
        s["hotkeys"]["build"] = ""   # user disabled
        save_settings(s)
        s2 = load_settings()
        assert s2["hotkeys"]["build"] == ""

    def test_reject_invalid_combo(self):
        s = default_config()
        s["hotkeys"]["research"] = "Ctrl+Shift"  # no key
        import pytest
        with pytest.raises(Exception):
            save_settings(s)

    def test_version_is_1(self):
        assert default_config()["version"] == 1


class TestFeatures:
    def test_new_upsert_get(self):
        f = Feature.new("add_session_logging", "/tmp/repo")
        upsert_feature(f)
        assert get_feature("add_session_logging") is not None
        assert get_feature("add_session_logging").target_repo == "/tmp/repo"

    def test_total_fires_advances(self):
        f = Feature.new("feat", "/tmp/repo")
        upsert_feature(f)
        mark_fired("feat", "research")
        mark_fired("feat", "plan")
        got = get_feature("feat")
        assert got is not None
        assert got.total_fires == 2
        assert got.last_fired_stage == "plan"

    def test_load_features_json(self, data_dir: Path):
        f1 = Feature.new("a", "/tmp/1")
        f2 = Feature.new("b", "/tmp/2")
        upsert_feature(f1)
        upsert_feature(f2)
        feats = load_features()
        assert [x.name for x in feats] == ["a", "b"]

    def test_unknown_feature(self):
        assert get_feature("nope") is None
