"""Tests for pilot security/planning republication task names."""
from __future__ import annotations


def test_pilot_context_task_names():
    assert "aia_etl.tasks.pilot_context.republish_security".endswith("republish_security")
    assert "aia_etl.tasks.pilot_context.republish_planning".endswith("republish_planning")
