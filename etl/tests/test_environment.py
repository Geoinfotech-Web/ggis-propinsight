"""Direct environmental pipeline formula tests."""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from aia_etl.gee import ENVIRONMENT_BANDS
from aia_etl.gee import _complete_dry_seasons as gee_dry_seasons
from aia_etl.sources.rasters import public_copernicus_dem_href
from aia_etl.tasks.environment import (
    _complete_dry_seasons,
    _read_gee_stack,
    landsat_clear_mask,
    landsat_surface_temperature_c,
    migration_components,
    percentile_ranks,
)


def test_three_most_recent_complete_dry_seasons():
    assert _complete_dry_seasons(date(2026, 8, 10)) == [
        (date(2023, 11, 1), date(2024, 3, 31)),
        (date(2024, 11, 1), date(2025, 3, 31)),
        (date(2025, 11, 1), date(2026, 3, 31)),
    ]


def test_current_incomplete_dry_season_is_not_used():
    assert _complete_dry_seasons(date(2026, 2, 1))[-1] == (
        date(2024, 11, 1),
        date(2025, 3, 31),
    )


def test_gee_uses_three_complete_dry_seasons_with_exclusive_end():
    assert gee_dry_seasons(date(2026, 8, 10)) == [
        (date(2023, 11, 1), date(2024, 4, 1)),
        (date(2024, 11, 1), date(2025, 4, 1)),
        (date(2025, 11, 1), date(2026, 4, 1)),
    ]


def test_cdse_dem_s3_asset_uses_public_cog_mirror():
    href = (
        "s3://eodata/auxdata/CopDEM_COG/copernicus-dem-30m/"
        "Copernicus_DSM_COG_10_N09_00_E007_00_DEM/"
        "Copernicus_DSM_COG_10_N09_00_E007_00_DEM.tif"
    )
    assert public_copernicus_dem_href(href) == (
        "https://copernicus-dem-30m.s3.amazonaws.com/"
        "Copernicus_DSM_COG_10_N09_00_E007_00_DEM/"
        "Copernicus_DSM_COG_10_N09_00_E007_00_DEM.tif"
    )


def test_landsat_surface_temperature_scaling():
    values = np.array([30_000], dtype="float32")
    assert landsat_surface_temperature_c(values)[0] == pytest.approx(-21.6094, abs=0.01)


def test_landsat_cloud_bits_are_excluded():
    qa = np.array([0, 0b10, 0b1000, 0b1_0000, 0b10_0000, 65_535], dtype="uint16")
    assert landsat_clear_mask(qa).tolist() == [True, False, False, False, False, False]


def test_percentile_ranks_preserve_missing_values():
    ranks = percentile_ranks(np.array([10.0, 20.0, np.nan, 30.0]))
    assert ranks[0] == 0
    assert ranks[1] == 50
    assert np.isnan(ranks[2])
    assert ranks[3] == 100


def test_migration_components_rank_growth_and_settlement_expansion():
    built_change, pop_rank, settlement_rank = migration_components(
        np.array([100.0, 100.0]),
        np.array([105.0, 130.0]),
        np.array([0.1, 0.1]),
        np.array([0.11, 0.2]),
    )
    assert built_change.tolist() == pytest.approx([10.0, 100.0])
    assert pop_rank.tolist() == [0.0, 100.0]
    assert settlement_rank.tolist() == [0.0, 100.0]


def test_gee_stack_reader_preserves_fixed_band_order(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    path = tmp_path / "environment.tif"
    values = np.stack(
        [np.full((2, 3), index + 1, dtype="float32") for index in range(len(ENVIRONMENT_BANDS))]
    )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=3,
        height=2,
        count=len(ENVIRONMENT_BANDS),
        dtype="float32",
        crs="EPSG:32632",
        transform=from_origin(300_000, 1_000_000, 250, 250),
    ) as output:
        output.write(values)

    transform, arrays = _read_gee_stack(path)

    assert tuple(arrays) == ENVIRONMENT_BANDS
    assert arrays["population_2025"][0, 0] == 1
    assert arrays["surface_temp_c"][0, 0] == len(ENVIRONMENT_BANDS)
    assert transform.a == 250
