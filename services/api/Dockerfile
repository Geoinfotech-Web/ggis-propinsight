FROM python:3.12-slim

# GDAL/PostGIS client libs land here as the ETL/raster work begins (Phase 1).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The editable install needs the package source present, so copy first.
# (.dockerignore keeps the host .venv and caches out of the image.)
COPY . .
RUN pip install --upgrade pip && pip install -e ".[dev]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
