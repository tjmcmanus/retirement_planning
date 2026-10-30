# Retirement Planning App (Streamlit) - container image
# Build:  podman build -t retirement-planning:local .
# The image contains code only. All user data lives on the /data volume.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    DATA_DIR=/data \
    STREAMLIT_THEME_PRIMARY_COLOR="#F63366" \
    STREAMLIT_THEME_BACKGROUND_COLOR="white"

# Non-root user. /data is created and owned by it BEFORE it is used as a named
# volume, so a fresh volume inherits this ownership (rootful and rootless).
RUN useradd --create-home --uid 1000 app \
    && mkdir /app /data \
    && chown app:app /data

WORKDIR /app

# Host-side tooling and test packages are not needed at runtime.
# constraints.txt pins every package (direct and transitive) to the verified versions,
# so rebuilds are reproducible instead of pulling newer majors that break the app.
COPY requirements.txt constraints.txt ./
RUN grep -vE '^(podman-compose|pytest)' requirements.txt > /tmp/requirements.runtime.txt \
    && pip install -c constraints.txt -r /tmp/requirements.runtime.txt \
    && rm /tmp/requirements.runtime.txt

COPY . /app
RUN chmod 755 /app/docker-entrypoint.sh

USER app

# Working directory is the data volume: modules that use cwd-relative paths
# (retirement_config.json, data/*.db, *.csv, config/*.yaml) read and write it.
WORKDIR /data
EXPOSE 8501 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["streamlit", "run", "/app/planning_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", \
     "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
