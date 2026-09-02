"""Admin GIS upload, validation, preview, publish and rollback endpoints."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.models import AdminAuditLog, GisUploadBatch, User
from app.state_readiness import (
    STATE_LAYER_NAMES,
    normalize_state_code,
    public_states,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"])

TARGETS = {"states", "lgas", "wards", "masterplans"}
TARGET_REGISTRY_LAYER = {
    "states": "admin_boundaries",
    "lgas": "admin_boundaries",
    "wards": "admin_boundaries",
    "masterplans": "masterplan",
}
POLYGON_TYPES = {"Polygon", "MultiPolygon"}
REQUIRED_FIELDS = {
    "states": ("code", "name"),
    "lgas": ("source_id", "name", "state_code"),
    "wards": ("source_id", "name", "area_council", "state_code"),
    "masterplans": ("source_id", "category", "state_code"),
}
VALID_CATEGORIES = {
    "residential",
    "industrial",
    "commercial",
    "institutional",
    "protected_reserve",
    "recreation_open_space",
    "agricultural",
    "military_restricted",
    "transportation",
    "construction_development",
    "extractive",
    "landfill",
    "cemetery",
    "other",
}


def _clean_target(value: str) -> str:
    target = value.strip().lower()
    if target not in TARGETS:
        raise HTTPException(status_code=422, detail=f"target_layer must be one of: {', '.join(sorted(TARGETS))}.")
    return target


def _clip(value: Any, max_len: int, fallback: str = "") -> str:
    text_value = str(value or fallback).strip()
    return text_value[:max_len] or fallback


def _mapping(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="attribute_mapping must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="attribute_mapping must be an object.")
    return {str(k): str(v) for k, v in parsed.items()}


def _prop(props: dict[str, Any], mapping: dict[str, str], key: str, fallback: Any = None) -> Any:
    candidates = [mapping.get(key), key, key.upper(), key.title(), key.replace("_", " ")]
    lowered = {str(k).lower(): v for k, v in props.items()}
    for candidate in candidates:
        if not candidate:
            continue
        if candidate in props and props[candidate] not in (None, ""):
            return props[candidate]
        value = lowered.get(candidate.lower())
        if value not in (None, ""):
            return value
    return fallback


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _feature_source_ids(collection: dict[str, Any], mapping: dict[str, str]) -> list[str]:
    ids: list[str] = []
    for index, feature in enumerate(collection.get("features") or []):
        props = feature.get("properties") or {}
        source_id = _clip(_prop(props, mapping, "source_id", feature.get("id") or f"feature-{index + 1}"), 160)
        ids.append(source_id)
    return ids


def _geojson_from_bytes(data: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="GeoJSON file could not be parsed.") from exc
    if parsed.get("type") == "Feature":
        parsed = {"type": "FeatureCollection", "features": [parsed]}
    if parsed.get("type") != "FeatureCollection" or not isinstance(parsed.get("features"), list):
        raise HTTPException(status_code=422, detail="Upload must be a GeoJSON FeatureCollection.")
    return parsed


def _shapefile_from_zip(data: bytes) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail="Shapefile upload must be a valid .zip archive.") from exc
    names = archive.namelist()
    lower = {name.lower(): name for name in names}
    required_suffixes = (".shp", ".shx", ".dbf", ".prj")
    missing = [suffix for suffix in required_suffixes if not any(name.endswith(suffix) for name in lower)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Shapefile zip is missing: {', '.join(missing)}.")
    prj_name = next(lower[name] for name in lower if name.endswith(".prj"))
    prj = archive.read(prj_name).decode("utf-8", errors="ignore").lower()
    if "wgs" not in prj and "4326" not in prj:
        raise HTTPException(status_code=422, detail="Shapefile CRS must be WGS84 / EPSG:4326.")
    try:
        import shapefile  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Shapefile support is not installed on this API image.") from exc
    shp_key = next(name for name in lower if name.endswith(".shp"))
    shx_key = next(name for name in lower if name.endswith(".shx"))
    dbf_key = next(name for name in lower if name.endswith(".dbf"))
    reader = shapefile.Reader(
        shp=io.BytesIO(archive.read(lower[shp_key])),
        shx=io.BytesIO(archive.read(lower[shx_key])),
        dbf=io.BytesIO(archive.read(lower[dbf_key])),
    )
    fields = [field[0] for field in reader.fields[1:]]
    features = []
    for index, shape_record in enumerate(reader.iterShapeRecords()):
        props = dict(zip(fields, shape_record.record, strict=False))
        features.append(
            {
                "type": "Feature",
                "id": props.get("source_id") or props.get("id") or index + 1,
                "geometry": shape_record.shape.__geo_interface__,
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _parse_upload(filename: str, data: bytes) -> tuple[str, dict[str, Any]]:
    lowered = filename.lower()
    if lowered.endswith(".zip"):
        return "shapefile_zip", _shapefile_from_zip(data)
    if lowered.endswith(".geojson") or lowered.endswith(".json"):
        return "geojson", _geojson_from_bytes(data)
    raise HTTPException(status_code=422, detail="Upload must be a zipped shapefile, .geojson or .json file.")


def _validate_collection(
    target: str,
    collection: dict[str, Any],
    mapping: dict[str, str],
    state_code: str | None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    features = collection.get("features") or []
    if not features:
        errors.append("No features found.")
    if len(features) > 25_000:
        errors.append("Upload contains more than 25,000 features; split it into smaller batches.")
    geometry_types: set[str] = set()
    detected_fields: set[str] = set()
    seen_source_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    required = REQUIRED_FIELDS[target]

    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            errors.append(f"Feature {index + 1} is not an object.")
            continue
        geometry = feature.get("geometry")
        props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        detected_fields.update(str(key) for key in props)
        if not geometry or not isinstance(geometry, dict):
            errors.append(f"Feature {index + 1} has an empty geometry.")
            continue
        geometry_type = str(geometry.get("type") or "")
        geometry_types.add(geometry_type)
        if geometry_type not in POLYGON_TYPES:
            errors.append(f"Feature {index + 1} has {geometry_type or 'unknown'} geometry; expected polygon boundaries.")
        if not geometry.get("coordinates"):
            errors.append(f"Feature {index + 1} has empty coordinates.")
        for field in required:
            if field == "state_code" and state_code:
                continue
            if _prop(props, mapping, field) in (None, ""):
                errors.append(f"Feature {index + 1} is missing required attribute '{field}'.")
        source_id = _prop(props, mapping, "source_id", feature.get("id"))
        if source_id:
            source_key = str(source_id).strip().lower()
            if source_key in seen_source_ids:
                duplicate_ids.add(str(source_id))
            seen_source_ids.add(source_key)
        if target == "masterplans":
            category = str(_prop(props, mapping, "category", "other")).strip().lower()
            if category and category not in VALID_CATEGORIES:
                warnings.append(
                    f"Feature {index + 1} category '{category}' will be normalized to 'other'."
                )

    if duplicate_ids:
        errors.append(f"Duplicate source_id values: {', '.join(sorted(duplicate_ids)[:10])}.")
    return {
        "publishable": not errors,
        "errors": errors,
        "warnings": warnings,
        "feature_count": len(features),
        "geometry_types": sorted(geometry_types),
        "required_fields": list(required),
        "detected_fields": sorted(detected_fields),
        "validated_at": datetime.now(UTC).isoformat(),
    }


async def _audit(
    session: AsyncSession,
    actor: User,
    action: str,
    target_type: str,
    target_id: str | None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        AdminAuditLog(
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload or {},
        )
    )


async def _update_state_readiness(session: AsyncSession, state_codes: set[str]) -> None:
    for code in state_codes:
        rows = await session.execute(
            text("SELECT layer, status FROM state_layer_registry WHERE state_code = :code"),
            {"code": code},
        )
        status_by_layer = {row.layer: row.status for row in rows}
        published = {layer for layer, status in status_by_layer.items() if status == "published"}
        core = {"admin_boundaries", "poi", "roads", "dem", "land_cover", "security", "market"}
        readiness = "ready" if core.issubset(published) else "partial" if published else "setup_required"
        await session.execute(
            text("UPDATE states SET readiness = :readiness, published = :published, updated_at = NOW() WHERE code = :code"),
            {"readiness": readiness, "published": readiness != "setup_required", "code": code},
        )


async def _bump_state_layer(
    session: AsyncSession,
    state_codes: set[str],
    target: str,
    version: str,
    source_name: str | None = None,
) -> None:
    layer = TARGET_REGISTRY_LAYER[target]
    for code in state_codes:
        await session.execute(
            text(
                """
                INSERT INTO state_layer_registry (state_code, layer, version, status, source, updated_at)
                VALUES (:state_code, :layer, :version, 'published', :source, NOW())
                ON CONFLICT (state_code, layer) DO UPDATE SET
                  version = EXCLUDED.version,
                  status = EXCLUDED.status,
                  source = EXCLUDED.source,
                  updated_at = NOW()
                """
            ),
            {"state_code": code, "layer": layer, "version": version, "source": source_name},
        )
        if layer == "masterplan":
            await session.execute(
                text(
                    """
                    INSERT INTO layer_registry (layer, version, source, notes, updated_at)
                    VALUES ('land_use', :version, :source, 'Includes admin-published masterplan areas.', NOW())
                    ON CONFLICT (layer) DO UPDATE SET
                      version = EXCLUDED.version,
                      source = EXCLUDED.source,
                      notes = EXCLUDED.notes,
                      updated_at = NOW()
                    """
                ),
                {"version": version, "source": source_name},
            )


async def _publish_features(session: AsyncSession, batch: GisUploadBatch, version: str) -> set[str]:
    target = batch.target_layer
    mapping = dict(batch.attribute_mapping or {})
    collection = dict(batch.feature_collection or {})
    state_codes: set[str] = set()
    for index, feature in enumerate(collection.get("features") or []):
        props = feature.get("properties") or {}
        geom_json = json.dumps(feature["geometry"])
        state_code = normalize_state_code(_prop(props, mapping, "state_code", batch.state_code)) or "FC"
        state_codes.add(state_code)
        source_id = _clip(_prop(props, mapping, "source_id", feature.get("id") or f"{target}-{batch.id}-{index + 1}"), 160)
        name = _clip(_prop(props, mapping, "name", _prop(props, mapping, "plan_name", source_id)), 240)
        if target == "states":
            code = normalize_state_code(_prop(props, mapping, "code", state_code)) or state_code
            state_codes.add(code)
            await session.execute(
                text(
                    """
                    WITH g AS (
                      SELECT ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)) AS geom
                    )
                    INSERT INTO states (
                      code, name, capital, centroid_lon, centroid_lat, bbox,
                      published, source, source_url, source_version, readiness, geom, updated_at
                    )
                    SELECT :code, :name, :capital, ST_X(ST_Centroid(g.geom)), ST_Y(ST_Centroid(g.geom)),
                           jsonb_build_array(ST_XMin(g.geom), ST_YMin(g.geom), ST_XMax(g.geom), ST_YMax(g.geom)),
                           TRUE, :source, :source_url, :version, 'partial', g.geom, NOW()
                    FROM g
                    ON CONFLICT (code) DO UPDATE SET
                      name = EXCLUDED.name,
                      capital = EXCLUDED.capital,
                      centroid_lon = EXCLUDED.centroid_lon,
                      centroid_lat = EXCLUDED.centroid_lat,
                      bbox = EXCLUDED.bbox,
                      published = TRUE,
                      source = EXCLUDED.source,
                      source_url = EXCLUDED.source_url,
                      source_version = EXCLUDED.source_version,
                      geom = EXCLUDED.geom,
                      updated_at = NOW()
                    """
                ),
                {
                    "geom": geom_json,
                    "code": code,
                    "name": _clip(_prop(props, mapping, "name", name), 80),
                    "capital": _clip(_prop(props, mapping, "capital", ""), 120, ""),
                    "source": batch.source_name,
                    "source_url": batch.source_url,
                    "version": version,
                },
            )
        elif target == "lgas":
            await session.execute(
                text(
                    """
                    INSERT INTO lgas (source_id, state_code, name, source, source_url, source_version, geom, updated_at)
                    VALUES (
                      :source_id, :state_code, :name, :source, :source_url, :version,
                      ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)), NOW()
                    )
                    ON CONFLICT (source_id) DO UPDATE SET
                      state_code = EXCLUDED.state_code,
                      name = EXCLUDED.name,
                      source = EXCLUDED.source,
                      source_url = EXCLUDED.source_url,
                      source_version = EXCLUDED.source_version,
                      geom = EXCLUDED.geom,
                      updated_at = NOW()
                    """
                ),
                {
                    "source_id": _clip(source_id, 120),
                    "state_code": state_code,
                    "name": _clip(name, 160),
                    "source": batch.source_name,
                    "source_url": batch.source_url,
                    "version": version,
                    "geom": geom_json,
                },
            )
        elif target == "wards":
            area_council = _clip(_prop(props, mapping, "area_council", _prop(props, mapping, "lga", "")), 160)
            await session.execute(
                text(
                    """
                    INSERT INTO wards (
                      source_id, state_code, name, area_council, state, source,
                      source_url, source_version, geom, updated_at
                    )
                    VALUES (
                      :source_id, :state_code, :name, :area_council,
                      (SELECT name FROM states WHERE code = :state_code),
                      :source, :source_url, :version,
                      ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)), NOW()
                    )
                    ON CONFLICT (source_id) DO UPDATE SET
                      state_code = EXCLUDED.state_code,
                      name = EXCLUDED.name,
                      area_council = EXCLUDED.area_council,
                      state = EXCLUDED.state,
                      source = EXCLUDED.source,
                      source_url = EXCLUDED.source_url,
                      source_version = EXCLUDED.source_version,
                      geom = EXCLUDED.geom,
                      updated_at = NOW()
                    """
                ),
                {
                    "source_id": _clip(source_id, 80),
                    "state_code": state_code,
                    "name": _clip(name, 160),
                    "area_council": area_council,
                    "source": batch.source_name,
                    "source_url": batch.source_url,
                    "version": version,
                    "geom": geom_json,
                },
            )
        elif target == "masterplans":
            category = str(_prop(props, mapping, "category", "other")).strip().lower()
            if category not in VALID_CATEGORIES:
                category = "other"
            effective_date = _parse_date(_prop(props, mapping, "effective_date"))
            params = {
                "source_id": source_id,
                "state_code": state_code,
                "plan_name": _clip(_prop(props, mapping, "plan_name", name), 240, ""),
                "category": category,
                "source_class": _clip(_prop(props, mapping, "source_class", ""), 120, ""),
                "source_doc": _clip(_prop(props, mapping, "source_doc", ""), 240, ""),
                "effective_date": effective_date,
                "source": batch.source_name,
                "source_url": batch.source_url,
                "version": version,
                "geom": geom_json,
            }
            await session.execute(
                text(
                    """
                    INSERT INTO masterplan_areas (
                      source_id, state_code, plan_name, category, source_class,
                      source_doc, effective_date, source, source_url, layer_version, geom, updated_at
                    )
                    VALUES (
                      :source_id, :state_code, :plan_name, :category, :source_class,
                      :source_doc, :effective_date, :source, :source_url, :version,
                      ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)), NOW()
                    )
                    ON CONFLICT (source_id) DO UPDATE SET
                      state_code = EXCLUDED.state_code,
                      plan_name = EXCLUDED.plan_name,
                      category = EXCLUDED.category,
                      source_class = EXCLUDED.source_class,
                      source_doc = EXCLUDED.source_doc,
                      effective_date = EXCLUDED.effective_date,
                      source = EXCLUDED.source,
                      source_url = EXCLUDED.source_url,
                      layer_version = EXCLUDED.layer_version,
                      geom = EXCLUDED.geom,
                      updated_at = NOW()
                    """
                ),
                params,
            )
            await session.execute(
                text(
                    """
                    INSERT INTO land_use_areas (
                      source_id, category, source_class, source_subtype, name,
                      designation, source, source_url, effective_date, layer_version, geom
                    )
                    VALUES (
                      :source_id, :category, :source_class, NULL, :plan_name,
                      'official_masterplan', :source, :source_url, :effective_date,
                      :version, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))
                    )
                    ON CONFLICT (source_id) DO UPDATE SET
                      category = EXCLUDED.category,
                      source_class = EXCLUDED.source_class,
                      name = EXCLUDED.name,
                      designation = EXCLUDED.designation,
                      source = EXCLUDED.source,
                      source_url = EXCLUDED.source_url,
                      effective_date = EXCLUDED.effective_date,
                      layer_version = EXCLUDED.layer_version,
                      geom = EXCLUDED.geom
                    """
                ),
                params,
            )
    return state_codes


async def _delete_batch_features(session: AsyncSession, batch: GisUploadBatch) -> set[str]:
    mapping = dict(batch.attribute_mapping or {})
    collection = dict(batch.feature_collection or {})
    state_codes: set[str] = set()
    source_ids = _feature_source_ids(collection, mapping)
    for feature in collection.get("features") or []:
        props = feature.get("properties") or {}
        code = normalize_state_code(_prop(props, mapping, "state_code", batch.state_code))
        if code:
            state_codes.add(code)
    if batch.target_layer == "states":
        for feature in collection.get("features") or []:
            props = feature.get("properties") or {}
            code = normalize_state_code(_prop(props, mapping, "code", _prop(props, mapping, "state_code", batch.state_code)))
            if code and code != "FC":
                await session.execute(
                    text("UPDATE states SET published = FALSE, readiness = 'setup_required', updated_at = NOW() WHERE code = :code"),
                    {"code": code},
                )
                state_codes.add(code)
    elif batch.target_layer == "lgas" and source_ids:
        await session.execute(text("DELETE FROM lgas WHERE source_id = ANY(:ids)"), {"ids": source_ids})
    elif batch.target_layer == "wards" and source_ids:
        await session.execute(text("DELETE FROM wards WHERE source_id = ANY(:ids)"), {"ids": [sid[:80] for sid in source_ids]})
    elif batch.target_layer == "masterplans" and source_ids:
        await session.execute(text("DELETE FROM masterplan_areas WHERE source_id = ANY(:ids)"), {"ids": source_ids})
        await session.execute(text("DELETE FROM land_use_areas WHERE source_id = ANY(:ids)"), {"ids": source_ids})
    return state_codes


@router.get("/states")
async def admin_states(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> list[dict[str, Any]]:
    return await public_states(session)


@router.post("/gis/uploads")
async def create_upload(
    target_layer: str = Form(...),
    source_name: str = Form(...),
    state_code: str | None = Form(None),
    source_url: str | None = Form(None),
    license_note: str | None = Form(None),
    attribute_mapping: str | None = Form(None),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict[str, Any]:
    target = _clean_target(target_layer)
    code = normalize_state_code(state_code)
    mapping = _mapping(attribute_mapping)
    data = await file.read()
    file_type, collection = _parse_upload(file.filename or "upload", data)
    validation = _validate_collection(target, collection, mapping, code)
    batch = GisUploadBatch(
        target_layer=target,
        state_code=code,
        file_name=file.filename or "upload",
        file_type=file_type,
        source_name=_clip(source_name, 160, "Unknown source"),
        source_url=source_url,
        license_note=license_note,
        status="validated" if validation["publishable"] else "blocked",
        validation_report=validation,
        attribute_mapping=mapping,
        feature_collection=collection,
        created_by=admin.id,
    )
    session.add(batch)
    await session.flush()
    await _audit(session, admin, "upload_validate", "gis_upload_batch", str(batch.id), validation)
    await session.commit()
    return {"id": batch.id, "status": batch.status, "validation_report": validation}


@router.get("/gis/uploads/{batch_id}")
async def upload_detail(
    batch_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> dict[str, Any]:
    batch = await session.get(GisUploadBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Upload batch not found.")
    return {
        "id": batch.id,
        "target_layer": batch.target_layer,
        "state_code": batch.state_code,
        "file_name": batch.file_name,
        "file_type": batch.file_type,
        "source_name": batch.source_name,
        "source_url": batch.source_url,
        "license_note": batch.license_note,
        "status": batch.status,
        "validation_report": batch.validation_report,
        "attribute_mapping": batch.attribute_mapping,
        "created_at": batch.created_at,
        "published_at": batch.published_at,
    }


@router.get("/gis/uploads/{batch_id}/preview")
async def upload_preview(
    batch_id: int,
    limit: int = 500,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> dict[str, Any]:
    batch = await session.get(GisUploadBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Upload batch not found.")
    collection = dict(batch.feature_collection or {})
    features = collection.get("features") or []
    return {**collection, "features": features[: max(1, min(limit, 2_000))]}


@router.post("/gis/uploads/{batch_id}/publish")
async def publish_upload(
    batch_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict[str, Any]:
    batch = await session.get(GisUploadBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Upload batch not found.")
    if batch.status not in {"validated", "published"} or not (batch.validation_report or {}).get("publishable"):
        raise HTTPException(status_code=409, detail="Upload batch is not publishable.")
    version = f"{datetime.now(UTC):%Y.%m.%d}.{batch.id}"
    state_codes = await _publish_features(session, batch, version)
    await _bump_state_layer(session, state_codes, batch.target_layer, version, batch.source_name)
    await _update_state_readiness(session, state_codes)
    report = dict(batch.validation_report or {})
    report["published_version"] = version
    batch.validation_report = report
    batch.status = "published"
    batch.published_at = datetime.now(UTC)
    await _audit(
        session,
        admin,
        "publish",
        "gis_upload_batch",
        str(batch.id),
        {"version": version, "states": sorted(state_codes), "target_layer": batch.target_layer},
    )
    await session.commit()
    return {"id": batch.id, "status": "published", "version": version, "states": sorted(state_codes)}


@router.post("/gis/uploads/{batch_id}/rollback")
async def rollback_upload(
    batch_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict[str, Any]:
    batch = await session.get(GisUploadBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Upload batch not found.")
    if batch.status != "published":
        raise HTTPException(status_code=409, detail="Only a published batch can be rolled back.")
    affected_states = await _delete_batch_features(session, batch)
    previous_result = await session.execute(
        select(GisUploadBatch)
        .where(
            GisUploadBatch.id != batch.id,
            GisUploadBatch.target_layer == batch.target_layer,
            GisUploadBatch.state_code == batch.state_code,
            GisUploadBatch.status == "published",
        )
        .order_by(GisUploadBatch.id.desc())
        .limit(1)
    )
    previous = previous_result.scalar_one_or_none()
    restored_version = None
    if previous is not None:
        restored_version = (previous.validation_report or {}).get("published_version") or f"rollback.{previous.id}"
        affected_states.update(await _publish_features(session, previous, str(restored_version)))
        await _bump_state_layer(session, affected_states, batch.target_layer, str(restored_version), previous.source_name)
    else:
        layer = TARGET_REGISTRY_LAYER[batch.target_layer]
        for code in affected_states:
            await session.execute(
                text(
                    """
                    UPDATE state_layer_registry
                    SET version = 'unpublished', status = 'unpublished', updated_at = NOW()
                    WHERE state_code = :state_code AND layer = :layer
                    """
                ),
                {"state_code": code, "layer": layer},
            )
    await _update_state_readiness(session, affected_states)
    batch.status = "rolled_back"
    await _audit(
        session,
        admin,
        "rollback",
        "gis_upload_batch",
        str(batch.id),
        {"states": sorted(affected_states), "restored_version": restored_version},
    )
    await session.commit()
    return {
        "id": batch.id,
        "status": "rolled_back",
        "states": sorted(affected_states),
        "restored_version": restored_version,
    }


@router.get("/gis/audit")
async def audit_log(
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT a.id, a.actor_id, u.email AS actor_email, a.action, a.target_type,
                   a.target_id, a.payload, a.created_at
            FROM admin_audit_log a
            LEFT JOIN users u ON u.id = a.actor_id
            ORDER BY a.id DESC
            LIMIT :limit
            """
        ),
        {"limit": max(1, min(limit, 500))},
    )
    return [dict(row._mapping) for row in result]


@router.get("/gis/layers")
async def gis_layers(_: User = Depends(require_admin)) -> dict[str, Any]:
    return {
        "targets": sorted(TARGETS),
        "state_layers": list(STATE_LAYER_NAMES),
        "required_fields": REQUIRED_FIELDS,
        "masterplan_categories": sorted(VALID_CATEGORIES),
    }
