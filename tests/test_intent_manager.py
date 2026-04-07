"""Tests for the Intent Manager."""

import pytest

from src.router.intent_manager import Intent


def test_intent_enum_values():
    assert Intent.DOCS.value == "DOCS"
    assert Intent.OPS.value == "OPS"
    assert Intent.HYBRID.value == "HYBRID"


def test_intent_from_string():
    assert Intent("DOCS") == Intent.DOCS
    assert Intent("OPS") == Intent.OPS
    assert Intent("HYBRID") == Intent.HYBRID


def test_intent_invalid_string():
    with pytest.raises(ValueError):
        Intent("INVALID")
