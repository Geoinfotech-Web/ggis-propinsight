# GDAL base gives us the system geospatial libraries (GDAL, PROJ, GEOS) that
# rasterio / rio-cogeo build against, plus gdal utilities used by the DEM tasks.
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.9.1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# osm2pgsql for the OSM roads & POIs pipeline; pip for Python deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip osm2pgsql osmium-tool \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /etl
COPY pyproject.toml ./
RUN pip install --break-system-packages -e ".[dev]"

COPY . .

# Default: run a Celery worker. docker-compose overrides for the beat scheduler.
CMD ["celery", "-A", "aia_etl.celery_app", "worker", "--loglevel=INFO"]
