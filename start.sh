#!/bin/bash
# Ensure PostgreSQL is running before starting brobot
PG_CTL="/home/linuxbrew/.linuxbrew/Cellar/postgresql@15/15.17/bin/pg_ctl"
PG_DATA="/home/linuxbrew/.linuxbrew/var/postgresql@15"
PSQL="/home/linuxbrew/.linuxbrew/Cellar/postgresql@15/15.17/bin/psql"

if ! $PSQL -U node -d polyedge -c "SELECT 1;" > /dev/null 2>&1; then
    echo "[start.sh] PostgreSQL not running, starting..."
    $PG_CTL start -D $PG_DATA -l /tmp/pg_brobot.log
    sleep 3
fi

echo "[start.sh] PostgreSQL OK. Starting brobot..."
exec .venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 6010
