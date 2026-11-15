# One image for both Cloud Run parts (see deploy/hochladen.ps1):
#   service olprep-api      : uvicorn api.main:app        (default command below)
#   job     olprep-auftrag  : python -m api.job           (command set when deploying the job)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # tile cache in /tmp (on Cloud Run /tmp is memory and gone after each job)
    OLPREP_CACHE=/tmp/cache \
    # public website: no OSM editing API as fallback for Overpass (OSM usage policy)
    OLPREP_OSM_API_ERSATZ=0

# rasterio's bundled GDAL needs the system's expat library (missing in the slim image)
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-cloud.txt ./
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements-cloud.txt

COPY src ./src
COPY api ./api
ENV PYTHONPATH=/app/src

# fail the build (not the start in the cloud) if a module cannot be imported
RUN python -c "import rasterio, pyproj, olprep.auftrag, api.main, api.job, api.cloud; \
from google.cloud import firestore, storage, run_v2; print('imports ok', rasterio.__gdal_version__)"

CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}
