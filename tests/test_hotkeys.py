"""Hotkey parsing / conflict / safe-fallback tests."""
from __future__ import annotations

import pytest

from passist.hotkeys import (
    DEFAULT_SAFE_FALLBACKS,
    conflict_within,
    is_valid,
    normalize_combination,
    parse,
    suggest_safe_fallback,
)


class TestParse:
    def test_simple_fkey(self):
        h = parse("F2")
        assert h.modifiers == frozenset()
        assert h.key == "F2"
        assert h.as_text() == "F2"

    def test_lowercase_fkey(self):
        assert parse("f2").as_text() == "F2"

    def test_three_mods(self):
        h = parse("Ctrl+Shift+Alt+P")
        assert h.modifiers == frozenset({"Ctrl", "Shift", "Alt"})
        assert h.key == "P"
        assert h.as_text() == "Ctrl+Alt+Shift+P"

    def test_digit_with_mods(self):
        assert parse("Ctrl+Shift+3").as_text() == "Ctrl+Shift+3"

    def test_case_insensitive_modifiers(self):
        assert parse("ctrl+shift+3").as_text() == "Ctrl+Shift+3"

    def test_single_letter_with_mods(self):
        h = parse("Ctrl+Shift+Q")
        assert h.key == "Q"

    def test_bad_fkey_range(self):
        with pytest.raises(ValueError, match="out of range"):
            parse("F25")

    def test_empty(self):
        with pytest.raises(ValueError, match="required"):
            parse("")

    def test_none(self):
        with pytest.raises(ValueError, match="required"):
            parse(None)  # type: ignore[arg-type]

    def test_mods_only(self):
        with pytest.raises(ValueError, match="no key"):
            parse("Ctrl+Shift")

    def test_multiple_keys(self):
        with pytest.raises(ValueError, match="multiple"):
            parse("Ctrl+Shift+F2+F3")


class TestIsvalid:
    def test_true(self):
        assert is_valid("F2")
        assert is_valid("Ctrl+Shift+3")
        assert is_valid("Ctrl+Alt+Q")

    def test_false(self):
        assert not is_valid("")
        assert not is_valid("Ctrl+Shift")
        assert not is_valid("F999")
        assert not is_valid("Ctrl+Shift+F2+F3")


class TestConflictWithin:
    def test_no_conflict(self):
        assert conflict_within({"research": "F2", "plan": "F3"}) == []

    def test_within_set_conflict(self):
        # Two stages bound to the same combo.
        assert set(conflict_within({"research": "F2", "plan": "F2"})) == {"research", "plan"}

    def test_disabled_no_count(self):
        assert conflict_within({"research": "F2", "plan": ""}) == []


class TestSafeFallbacks:
    def test_known_stage(self):
        assert suggest_safe_fallback("research") == "Ctrl+Shift+1"
        assert suggest_safe_fallback("check-plan") == "Ctrl+Shift+3"

    def test_unknown_stage(self):
        assert suggest_safe_fallback("unknown") is None

    def test_all_six_stages_have_fallback(self):
        for stage in ("research", "plan", "check-plan", "build", "continue", "review-code"):
            assert stage in DEFAULT_SAFE_FALLBACKS
