#!/usr/bin/env bash
# Download AdventureWorks CSVs, convert, load into Postgres, apply wh views.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKDIR="${WORKDIR:-/tmp/aw-load}"
DBURL="${DATABASE_URL:-host=127.0.0.1 port=5432 dbname=Adventureworks user=postgres password=postgres}"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

if [[ ! -d AdventureWorks-for-Postgres ]]; then
  git clone --depth 1 https://github.com/lorint/AdventureWorks-for-Postgres.git
fi
if [[ ! -f AdventureWorks-oltp-install-script.zip ]]; then
  curl -fsSL -o AdventureWorks-oltp-install-script.zip \
    https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorks-oltp-install-script.zip
fi
unzip -qo AdventureWorks-oltp-install-script.zip -d aw-data
cp aw-data/*.csv AdventureWorks-for-Postgres/
cd AdventureWorks-for-Postgres
ruby update_csvs.rb
# parse DBURL loosely for psql
export PGPASSWORD="${PGPASSWORD:-postgres}"
psql $DBURL -c 'SELECT 1' >/dev/null
psql $DBURL -c 'DROP DATABASE IF EXISTS "Adventureworks";' || true
# When DATABASE_URL already points at Adventureworks, create via maintenance db
psql $(echo "$DBURL" | sed 's/dbname=Adventureworks/dbname=postgres/') -c 'CREATE DATABASE "Adventureworks";' 2>/dev/null || \
  psql -h 127.0.0.1 -U postgres -d postgres -c 'CREATE DATABASE "Adventureworks";' || true
psql $DBURL -f install.sql
psql $DBURL -f "$ROOT/sql/01_create_wh_views.sql"
echo "Loaded AdventureWorks + wh views."
