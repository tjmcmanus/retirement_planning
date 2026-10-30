#!/bin/sh
# Seeds the data volume with default reference files (never overwrites existing
# files), then runs the command. Runs as the unprivileged "app" user.
set -eu

APP_DIR=/app
DATA_DIR="${DATA_DIR:-/data}"

mkdir -p "$DATA_DIR/data" "$DATA_DIR/config"

if [ ! -w "$DATA_DIR" ]; then
    echo "ERROR: $DATA_DIR is not writable by uid $(id -u). If the volume was created" >&2
    echo "by an earlier run as another user, recreate it or add the ':U' volume option." >&2
    exit 1
fi

# Tax / reference tables and templates the app reads relative to the working dir.
for f in atm.csv cap_gains.csv fica_limits.csv income_rates.csv ira_limits.csv \
         irmaa.csv medicare_premiums.csv qbi_limits.csv rmd.csv ssincome.csv \
         standard.csv retirement_config.json.example; do
    if [ ! -e "$DATA_DIR/$f" ] && [ -e "$APP_DIR/$f" ]; then
        cp "$APP_DIR/$f" "$DATA_DIR/$f"
        echo "seeded $f"
    fi
done

for f in "$APP_DIR"/config/*.yaml; do
    [ -e "$f" ] || continue
    b=$(basename "$f")
    if [ ! -e "$DATA_DIR/config/$b" ]; then
        cp "$f" "$DATA_DIR/config/$b"
        echo "seeded config/$b"
    fi
done

cd "$DATA_DIR"
exec "$@"
