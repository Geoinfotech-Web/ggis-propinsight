# GDAL base gives us the system geospatial libraries (GDAL, PROJ, GEOS) that
# rasterio / rio-cogeo build against, plus gdal utilities used by the DEM tasks.
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.9.1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# osm2pgsql/osmium for the OSM pipeline; venv tooling for an isolated install.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip python3-venv osm2pgsql osmium-tool \
    && rm -rf /var/lib/apt/lists/*

# Install into a clean virtualenv so pip never fights the GDAL base image's
# Debian-managed numpy (rasterio's manylinux wheel bundles its own GDAL).
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /etl
# The editable install needs the package source present, so copy first.
# (.dockerignore keeps the host .venv and caches out of the image.)
COPY . .
RUN pip install --upgrade pip && pip install -e ".[dev]"

# Default: run a Celery worker. docker-compose overrides for the beat scheduler.
CMD ["celery", "-A", "aia_etl.celery_app", "worker", "--loglevel=INFO"]
