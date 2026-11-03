#!/bin/bash
# Start the containerized Retirement Planning app with Podman or Docker (macOS / Linux).
# Usage: ./start.sh [up|down|logs|rebuild|restart]
#
# Runtime selection: set CONTAINER_RUNTIME=podman|docker to force one. Otherwise podman is
# used when installed, falling back to docker. Other Docker-compatible engines (Rancher
# Desktop, Colima, OrbStack) work through the `docker` CLI.
set -euo pipefail
cd "$(dirname "$0")"

CMD="${1:-up}"
URL="http://localhost:8501"          # Streamlit (legacy UI)
WEB_URL="http://localhost:8000"      # HTML front end + API

RUNTIME="${CONTAINER_RUNTIME:-}"
if [ -z "$RUNTIME" ]; then
    if command -v podman >/dev/null 2>&1; then RUNTIME=podman
    elif command -v docker >/dev/null 2>&1; then RUNTIME=docker
    else echo "Error: neither podman nor docker found on PATH." >&2; exit 1
    fi
fi

case "$RUNTIME" in
    podman)
        command -v podman >/dev/null 2>&1 || { echo "Error: podman not found on PATH." >&2; exit 1; }
        # `podman compose` otherwise picks the first provider on PATH (e.g. Rancher's docker-compose).
        export PODMAN_COMPOSE_PROVIDER=podman-compose
        export PODMAN_COMPOSE_WARNING_LOGS=false
        command -v podman-compose >/dev/null 2>&1 || { echo "Error: podman-compose not found (pip/brew install podman-compose)." >&2; exit 1; }
        COMPOSE=(podman compose)
        # macOS/Windows run containers inside a VM; start it if needed.
        if [ "$(uname -s)" = "Darwin" ] || [ -n "${PODMAN_FORCE_MACHINE:-}" ]; then
            if ! podman info >/dev/null 2>&1; then
                echo "Starting Podman machine..."
                podman machine start
            fi
        fi
        ;;
    docker)
        command -v docker >/dev/null 2>&1 || { echo "Error: docker not found on PATH." >&2; exit 1; }
        if docker compose version >/dev/null 2>&1; then
            COMPOSE=(docker compose)
        elif command -v docker-compose >/dev/null 2>&1; then
            COMPOSE=(docker-compose)
        else
            echo "Error: Docker Compose not found (need the 'docker compose' plugin or docker-compose)." >&2; exit 1
        fi
        docker info >/dev/null 2>&1 || { echo "Error: the Docker daemon is not running. Start Docker (or Rancher Desktop/Colima/OrbStack) and retry." >&2; exit 1; }
        ;;
    *)
        echo "Error: CONTAINER_RUNTIME must be 'podman' or 'docker' (got '$RUNTIME')." >&2; exit 1
        ;;
esac
echo "Using container runtime: $RUNTIME (${COMPOSE[*]})"

# First start: create .env from the template. It is git-ignored and holds secrets, so it is never checked in.
if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    echo "Created .env from .env.example. Replace the placeholder values (or import a backup bundle" >&2
    echo "that contains your .env) and run ./start.sh again for them to take effect." >&2
fi

case "$CMD" in
    up|rebuild|restart)
        if [ "$CMD" = "rebuild" ]; then
            "${COMPOSE[@]}" build --no-cache
        fi
        # --force-recreate on rebuild so a new image replaces the running container
        # restart = recreate the containers without rebuilding: picks up a changed .env
        FORCE=()
        if [ "$CMD" = "rebuild" ] || [ "$CMD" = "restart" ]; then FORCE=(--force-recreate); fi
        "${COMPOSE[@]}" up -d --build ${FORCE[@]+"${FORCE[@]}"}
        echo -n "Waiting for the apps to become healthy"
        for _ in $(seq 1 60); do
            if curl -fsS "$URL/_stcore/health" >/dev/null 2>&1 \
               && curl -fsS "$WEB_URL/api/health" >/dev/null 2>&1; then
                echo; echo "Ready:"
                echo "  HTML app:      $WEB_URL"
                echo "  Streamlit app: $URL"
                if command -v open >/dev/null 2>&1; then open "$WEB_URL"
                elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$WEB_URL" >/dev/null 2>&1 || true
                fi
                exit 0
            fi
            echo -n "."; sleep 2
        done
        echo; echo "App did not become healthy in time. See: ./start.sh logs" >&2
        exit 1
        ;;
    down)  "${COMPOSE[@]}" down ;;
    logs)  "${COMPOSE[@]}" logs -f ;;
    *)     echo "Usage: $0 [up|down|logs|rebuild|restart]" >&2; exit 2 ;;
esac
