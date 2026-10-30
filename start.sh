#!/bin/bash
# Start the containerized Retirement Planning app with Podman (macOS / Linux).
# Usage: ./start.sh [up|down|logs|rebuild]
set -euo pipefail
cd "$(dirname "$0")"

CMD="${1:-up}"
URL="http://localhost:8501"          # Streamlit (legacy UI)
WEB_URL="http://localhost:8000"      # HTML front end + API

command -v podman >/dev/null 2>&1 || { echo "Error: podman not found on PATH." >&2; exit 1; }

# `podman compose` otherwise picks the first provider on PATH (e.g. Rancher's docker-compose).
export PODMAN_COMPOSE_PROVIDER=podman-compose
export PODMAN_COMPOSE_WARNING_LOGS=false
command -v podman-compose >/dev/null 2>&1 || { echo "Error: podman-compose not found (pip/brew install podman-compose)." >&2; exit 1; }

# macOS/Windows run containers inside a VM; start it if needed.
if [ "$(uname -s)" = "Darwin" ] || [ -n "${PODMAN_FORCE_MACHINE:-}" ]; then
    if ! podman info >/dev/null 2>&1; then
        echo "Starting Podman machine..."
        podman machine start
    fi
fi

case "$CMD" in
    up|rebuild)
        if [ ! -f .env ]; then
            echo "Error: .env not found. Copy .env.example to .env and set ENCRYPTION_KEY." >&2
            exit 1
        fi
        if [ "$CMD" = "rebuild" ]; then
            podman compose build --no-cache
        fi
        # --force-recreate on rebuild so a new image replaces the running container
        if [ "$CMD" = "rebuild" ]; then FORCE="--force-recreate"; else FORCE=""; fi
        podman compose up -d --build $FORCE
        echo -n "Waiting for the apps to become healthy"
        for _ in $(seq 1 60); do
            if curl -fsS "$URL/_stcore/health" >/dev/null 2>&1 \
               && curl -fsS "$WEB_URL/api/health" >/dev/null 2>&1; then
                echo; echo "Ready:"
                echo "  HTML app:      $WEB_URL"
                echo "  Streamlit app: $URL"
                if command -v open >/dev/null 2>&1; then open "$WEB_URL"; fi
                exit 0
            fi
            echo -n "."; sleep 2
        done
        echo; echo "App did not become healthy in time. See: ./start.sh logs" >&2
        exit 1
        ;;
    down)  podman compose down ;;
    logs)  podman compose logs -f ;;
    *)     echo "Usage: $0 [up|down|logs|rebuild]" >&2; exit 2 ;;
esac
