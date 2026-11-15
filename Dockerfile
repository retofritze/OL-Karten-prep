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

WORKDIR /app
COPY requirements-cloud.txt ./
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY src ./src
COPY api ./api
ENV PYTHONPATH=/app/src

CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}
