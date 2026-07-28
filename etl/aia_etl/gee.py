"""Google Earth Engine integration — DEM and remote-sensing analysis (Overview §6.3).

Auth is service-account based (GEE_SERVICE_ACCOUNT_EMAIL + GEE_SERVICE_ACCOUNT_KEY).
The key value may be either a path to the JSON key file or the JSON content itself.
`earthengine-api` is imported lazily so this module loads without it present, and
the "not configured" path raises before any EE import.

Exports use `getDownloadURL`, which caps at a few tens of MB. For an AOI larger
than that (e.g. all of FCT at 30 m) tile the AOI or export to GCS — see
`export_dem_cop30`'s note.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests

from aia_etl.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

BBox = tuple[float, float, float, float]

_initialised = False


def _project_from_email(email: str) -> str | None:
    """Parse the Cloud project from a service-account email.

    >>> _project_from_email("aia-etl@ggis-propinsight.iam.gserviceaccount.com")
    'ggis-propinsight'
    """
    try:
        domain = email.split("@", 1)[1]
        if domain.endswith(".iam.gserviceaccount.com"):
            return domain.split(".", 1)[0]
    except IndexError:
        return None
    return None


def init_ee() -> None:
    """Initialise Earth Engine with the configured service account (idempotent)."""
    global _initialised
    if _initialised:
        return

    email = settings.gee_service_account_email
    key = settings.gee_service_account_key
    if not email or not key:
        raise RuntimeError(
            "GEE not configured: set GEE_SERVICE_ACCOUNT_EMAIL and GEE_SERVICE_ACCOUNT_KEY"
        )

    import ee  # lazy — only needed when actually talking to EE

    if key.strip().startswith("{"):
        creds = ee.ServiceAccountCredentials(email, key_data=key)
    elif Path(key).exists():
        creds = ee.ServiceAccountCredentials(email, key_file=key)
    else:
        # Treat as JSON content that simply isn't brace-prefixed by whitespace.
        creds = ee.ServiceAccountCredentials(email, key_data=key)

    project = settings.gee_project or _project_from_email(email)
    ee.Initialize(creds, project=project)
    _initialised = True
    log.info("Earth Engine initialised (project=%s)", project)


def _download(url: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(out_path, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    return out_path


def export_dem_cop30(bbox: BBox, out_path: Path, scale: int = 30) -> Path:
    """Export a Copernicus GLO-30 DEM mosaic for the AOI to a local GeoTIFF.

    NOTE: for AOIs beyond the getDownloadURL size cap, tile `bbox` and mosaic the
    results, or switch to an `ee.batch.Export.image.toCloudStorage` task.
    """
    init_ee()
    import ee

    region = ee.Geometry.Rectangle(list(bbox))
    dem = ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM").mosaic().clip(region)
    url = dem.getDownloadURL(
        {"region": region, "scale": scale, "format": "GEO_TIFF", "crs": "EPSG:4326"}
    )
    log.info("exporting Copernicus GLO-30 DEM for %s at %sm", bbox, scale)
    return _download(url, out_path)


def export_s2_composite(
    bbox: BBox, out_path: Path, start: str, end: str, scale: int = 10, max_cloud: int = 20
) -> Path:
    """Export a cloud-masked Sentinel-2 median composite (RGB+NIR) for the AOI.

    Feeds later analysis (vegetation/NDVI for environmental nuisance & feasibility).
    """
    init_ee()
    import ee

    region = ee.Geometry.Rectangle(list(bbox))

    def _mask(img: Any) -> Any:
        scl = img.select("SCL")
        keep = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return img.updateMask(keep)

    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        .map(_mask)
    )
    composite = coll.median().select(["B4", "B3", "B2", "B8"]).clip(region)
    url = composite.getDownloadURL(
        {"region": region, "scale": scale, "format": "GEO_TIFF", "crs": "EPSG:4326"}
    )
    log.info("exporting Sentinel-2 composite %s..%s for %s", start, end, bbox)
    return _download(url, out_path)
