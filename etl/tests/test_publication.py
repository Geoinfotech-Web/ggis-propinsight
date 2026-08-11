"""Regression tests for safe ETL publication boundaries."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from types import ModuleType

import pytest

from aia_etl.sources.base import PoiRecord


class _InlineTaskApp:
    """Small Celery stand-in so pure orchestration tests need no worker dependency."""

    def task(self, **kwargs):  # noqa: ANN003, ANN201
        def decorate(func):  # noqa: ANN001, ANN202
            func.run = func
            return func

        return decorate


_celery_app = ModuleType("aia_etl.celery_app")
_celery_app.app = _InlineTaskApp()  # type: ignore[attr-defined]
sys.modules.setdefault("aia_etl.celery_app", _celery_app)

_db = ModuleType("aia_etl.db")
_db.connect = None  # type: ignore[attr-defined]
sys.modules.setdefault("aia_etl.db", _db)

from aia_etl.tasks import amenities, dem, flood_tiles  # noqa: E402


def test_multi_source_fetch_completes_before_publish(monkeypatch):
    events: list[str] = []

    def fake_fetch(source, bbox):  # noqa: ANN001
        events.append(f"fetch:{source}")
        offset = 0.01 if source == "overture" else 0.0
        return [PoiRecord(7.49 + offset, 9.06, "school", source, source)]

    class FakeConnection:
        def execute(self, statement):  # noqa: ANN001, ANN201
            return None

    @contextmanager
    def fake_connect():
        events.append("transaction:begin")
        yield FakeConnection()
        events.append("transaction:commit")

    def fake_replace(conn, source, records, version):  # noqa: ANN001
        events.append(f"replace:{source}:{version}")
        return len(records)

    def fake_bump(conn, layer, source=None, notes=None):  # noqa: ANN001
        events.append(f"bump:{layer}")
        return "2026.08.1", 3

    monkeypatch.setattr(amenities, "_fetch", fake_fetch)
    monkeypatch.setattr(amenities, "connect", fake_connect)
    monkeypatch.setattr(amenities, "next_layer_version", lambda conn, layer: "2026.08.1")
    monkeypatch.setattr(amenities, "replace_source_pois", fake_replace)
    monkeypatch.setattr(amenities, "bump_layer", fake_bump)

    result = amenities.refresh_amenities.run(
        sources=["overpass", "overture"], bbox=[6.75, 8.25, 7.75, 9.35]
    )

    assert events[:2] == ["fetch:overpass", "fetch:overture"]
    assert events[2:] == [
        "transaction:begin",
        "replace:overpass:2026.08.1",
        "replace:overture:2026.08.1",
        "bump:poi",
        "transaction:commit",
    ]
    assert result["total_pois"] == 2
    assert result["scores_invalidated"] == 3


def test_provider_failure_preserves_it_and_publishes_healthy_sources(monkeypatch):
    events: list[str] = []

    def fake_fetch(source, bbox):  # noqa: ANN001
        if source == "overture":
            raise RuntimeError("provider unavailable")
        return [PoiRecord(7.49, 9.06, "school", "School", source)]

    class FakeConnection:
        def execute(self, statement):  # noqa: ANN001, ANN201
            return None

    @contextmanager
    def fake_connect():
        events.append("transaction:begin")
        yield FakeConnection()
        events.append("transaction:commit")

    def fake_replace(conn, source, records, version):  # noqa: ANN001
        events.append(f"replace:{source}")
        return len(records)

    def fake_bump(conn, layer, source=None, notes=None):  # noqa: ANN001
        events.append(f"bump:{layer}")
        return "2026.08.1", 1

    monkeypatch.setattr(amenities, "_fetch", fake_fetch)
    monkeypatch.setattr(amenities, "connect", fake_connect)
    monkeypatch.setattr(amenities, "next_layer_version", lambda conn, layer: "2026.08.1")
    monkeypatch.setattr(amenities, "replace_source_pois", fake_replace)
    monkeypatch.setattr(amenities, "bump_layer", fake_bump)

    result = amenities.refresh_amenities.run(
        sources=["overpass", "overture"], bbox=[6.75, 8.25, 7.75, 9.35]
    )

    assert events == [
        "transaction:begin",
        "replace:overpass",
        "bump:poi",
        "transaction:commit",
    ]
    assert result["sources"] == {"overpass": 1}
    assert result["errors"] == {"overture": "provider unavailable"}


def test_all_provider_failures_never_open_publish_transaction(monkeypatch):
    def fake_fetch(source, bbox):  # noqa: ANN001
        raise RuntimeError(f"{source} unavailable")

    def unexpected_connect():
        raise AssertionError("publication transaction must not open")

    monkeypatch.setattr(amenities, "_fetch", fake_fetch)
    monkeypatch.setattr(amenities, "connect", unexpected_connect)

    with pytest.raises(RuntimeError, match="all amenity providers failed"):
        amenities.refresh_amenities.run(
            sources=["overpass", "overture"], bbox=[6.75, 8.25, 7.75, 9.35]
        )


def test_geographic_dem_stride_is_about_one_kilometre():
    row_stride, col_stride = dem._sample_strides(
        0.0002695,
        0.0002695,
        geographic=True,
        mid_lat=9.0,
        spacing_m=1_000,
    )
    assert 32 <= row_stride <= 35
    assert 32 <= col_stride <= 35


def test_dem_derivatives_publishable_sampling(tmp_path):
    numpy = pytest.importorskip("numpy")
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    profile = {
        "driver": "GTiff",
        "height": 100,
        "width": 100,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(7.45, 9.10, 0.0002695, 0.0002695),
        "nodata": -9999.0,
    }
    paths = [tmp_path / name for name in ("dem.tif", "slope.tif", "twi.tif")]
    arrays = [
        numpy.full((100, 100), 480.0, dtype="float32"),
        numpy.full((100, 100), numpy.pi / 4, dtype="float32"),
        numpy.full((100, 100), 6.5, dtype="float32"),
    ]
    for path, data in zip(paths, arrays, strict=True):
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(data, 1)

    samples = dem.sample_dem_derivatives(*paths, spacing_m=1_000)

    assert len(samples) == 9
    assert samples[0]["elevation_m"] == pytest.approx(480.0)
    assert samples[0]["slope_deg"] == pytest.approx(45.0)
    assert samples[0]["twi"] == pytest.approx(6.5)
    assert 7.45 <= samples[0]["lon"] <= 7.48
    assert 9.07 <= samples[0]["lat"] <= 9.10


def test_flow_accumulation_runs_with_pinned_numba(tmp_path):
    numpy = pytest.importorskip("numpy")
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    source = tmp_path / "sloping-dem.tif"
    output = tmp_path / "flow.tif"
    profile = {
        "driver": "GTiff",
        "height": 20,
        "width": 20,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(7.45, 9.10, 0.0002695, 0.0002695),
        "nodata": -9999.0,
    }
    values = numpy.add.outer(
        numpy.arange(20, 0, -1, dtype="float32"),
        numpy.arange(20, 0, -1, dtype="float32"),
    )
    with rasterio.open(source, "w", **profile) as destination:
        destination.write(values, 1)

    dem.compute_flow_accumulation(source, output)

    with rasterio.open(output) as result:
        accumulation = result.read(1)
    assert numpy.isfinite(accumulation).all()
    assert accumulation.max() > 1


def test_hazard_stub_does_not_publish_a_fake_version(monkeypatch):
    monkeypatch.setattr(flood_tiles, "fetch_model_version", lambda: "ggis-fw-2.4")
    monkeypatch.setattr(flood_tiles, "current_hazard_version", lambda: "unpublished")

    result = flood_tiles.mirror_hazard_tiles.run()

    assert result["status"] == "blocked"
    assert result["hazard_version"] == "unpublished"
    assert result["remote_version"] == "ggis-fw-2.4"
