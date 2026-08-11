"""Tests for the GEE integration's pure logic (no earthengine-api required)."""
from __future__ import annotations

import pytest

from aia_etl.gee import _bbox_tiles, _project_from_email, init_ee


def test_project_parsed_from_service_account_email():
    assert (
        _project_from_email("aia-etl@ggis-propinsight.iam.gserviceaccount.com")
        == "ggis-propinsight"
    )


def test_project_from_email_handles_non_sa_addresses():
    assert _project_from_email("someone@example.com") is None
    assert _project_from_email("garbage") is None


def test_fct_environment_export_is_split_into_four_bounded_tiles():
    tiles = _bbox_tiles((6.75, 8.25, 7.75, 9.35))

    assert len(tiles) == 4
    assert max(east - west for west, _, east, _ in tiles) <= 0.55
    assert max(north - south for _, south, _, north in tiles) <= 0.550_001


def test_init_ee_raises_when_unconfigured(monkeypatch):
    # Blank out credentials; init must fail before importing earthengine-api.
    from aia_etl import gee

    monkeypatch.setattr(gee.settings, "gee_service_account_email", None)
    monkeypatch.setattr(gee.settings, "gee_service_account_key", None)
    monkeypatch.setattr(gee, "_initialised", False)

    with pytest.raises(RuntimeError, match="GEE not configured"):
        init_ee()
