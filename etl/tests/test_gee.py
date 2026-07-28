"""Tests for the GEE integration's pure logic (no earthengine-api required)."""
from __future__ import annotations

import pytest

from aia_etl.gee import _project_from_email, init_ee


def test_project_parsed_from_service_account_email():
    assert (
        _project_from_email("aia-etl@ggis-propinsight.iam.gserviceaccount.com")
        == "ggis-propinsight"
    )


def test_project_from_email_handles_non_sa_addresses():
    assert _project_from_email("someone@example.com") is None
    assert _project_from_email("garbage") is None


def test_init_ee_raises_when_unconfigured(monkeypatch):
    # Blank out credentials; init must fail before importing earthengine-api.
    from aia_etl import gee

    monkeypatch.setattr(gee.settings, "gee_service_account_email", None)
    monkeypatch.setattr(gee.settings, "gee_service_account_key", None)
    monkeypatch.setattr(gee, "_initialised", False)

    with pytest.raises(RuntimeError, match="GEE not configured"):
        init_ee()
