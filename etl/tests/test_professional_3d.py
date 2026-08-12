"""Tests for analytical building and canopy preparation."""
from __future__ import annotations

from aia_etl.sources.canopy import minimum_canopy_pixels, tree_class_values
from aia_etl.sources.overture_buildings import (
    build_sql,
    feature_type_sql,
    iter_overture_building_batches,
    records_from_rows,
    resolve_display_height,
    tiled_bboxes,
)


def test_building_height_precedence_is_explicit():
    assert resolve_display_height(14.5, 3) == (14.5, "published_height")
    assert resolve_display_height(None, 3) == (9.600000000000001, "floors_derived")
    assert resolve_display_height(None, None) == (6.0, "default_visual")


def test_building_parts_replace_parent_without_losing_standalone_buildings():
    polygon = '{"type":"Polygon","coordinates":[[[7,9],[7.1,9],[7.1,9.1],[7,9]]]} '
    rows = [
        ("parent", "building", "office", 20.0, 6, None, None, True, "[]", polygon),
        ("part", "building_part", "office", 12.0, 4, None, "parent", None, "[]", polygon),
        ("standalone", "building", "house", None, None, None, None, False, "[]", polygon),
    ]
    records = records_from_rows(rows)
    assert [record.source_id for record in records] == ["part", "standalone"]
    assert records[1].height_basis == "default_visual"


def test_overture_building_query_reads_both_feature_types_and_sources():
    sql = build_sql((6.75, 8.25, 7.75, 9.35), "2026-07-22.0")
    assert "theme=buildings/type=*" in sql
    assert "union_by_name=true" in sql
    assert "to_json(sources)" in sql
    assert "ST_IsValid(geometry)" in sql


def test_tree_classes_support_dynamic_world_and_worldcover_names():
    assert tree_class_values({1: {"key": "trees"}, 2: {"key": "grass"}}) == {1}
    assert tree_class_values({10: {"key": "tree_cover"}, 20: {"key": "shrub"}}) == {10}
    assert minimum_canopy_pixels(10) == 25
    assert minimum_canopy_pixels(20) == 7


def test_streaming_building_batches_reject_invalid_batch_size():
    try:
        iter_overture_building_batches((6.75, 8.25, 7.75, 9.35), "2026-07-22.0", batch_size=0)
    except ValueError as error:
        assert "positive" in str(error)
    else:
        raise AssertionError("invalid batch size should be rejected before network access")


def test_type_specific_queries_normalize_the_different_overture_schemas():
    part_sql = feature_type_sql(
        (6.75, 8.25, 7.75, 9.35), "2026-07-22.0", "building_part"
    )
    building_sql = feature_type_sql(
        (6.75, 8.25, 7.75, 9.35), "2026-07-22.0", "building"
    )
    assert "CAST(NULL AS VARCHAR) AS class" in part_sql
    assert "building_id AS building_id" in part_sql
    assert "CAST(NULL AS VARCHAR) AS building_id" in building_sql
    assert "has_parts AS has_parts" in building_sql


def test_large_fct_bbox_is_split_into_non_overlapping_scan_tiles():
    tiles = tiled_bboxes((6.0, 8.0, 8.0, 10.0), divisions=2)
    assert tiles == (
        (6.0, 8.0, 7.0, 9.0),
        (7.0, 8.0, 8.0, 9.0),
        (6.0, 9.0, 7.0, 10.0),
        (7.0, 9.0, 8.0, 10.0),
    )
