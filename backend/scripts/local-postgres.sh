#!/usr/bin/env bash
# Bring up the local Postgres this backend develops and tests against.
#
# The backend's real database is Supabase-hosted Postgres, so everything it
# writes has to be exercised against Postgres - not against a stand-in that
# happens to speak enough SQL to pass. DuckDB stays where it belongs, in the
# analytics pipeline (pipeline/), and no longer backs the API's dev/test path.
#
# Idempotent by design: run it as often as you like. It starts a server if one
# isn't already listening, then creates the role and the two databases only if
# they're missing. Nothing here drops anything.
#
# Two ways to get a server, tried in this order:
#
#   native  - a Postgres installed on the machine (Debian/Ubuntu's clustered
#             layout via pg_ctlcluster, or anything already listening on the
#             port). This is what the Claude Code web sandbox has, and the
#             fastest path anywhere it exists.
#   docker  - `docker compose` against ../docker-compose.yml, for machines
#             with Docker but no local Postgres install.
#
# Force one with OURHIKE_PG_MODE=native|docker if the auto-detection picks
# wrong.
set -euo pipefail

PG_HOST=${OURHIKE_PG_HOST:-localhost}
PG_PORT=${OURHIKE_PG_PORT:-5432}
PG_USER=${OURHIKE_PG_USER:-ourhike}
PG_PASSWORD=${OURHIKE_PG_PASSWORD:-ourhike}
DEV_DB=${OURHIKE_PG_DEV_DB:-ourhike_dev}
TEST_DB=${OURHIKE_PG_TEST_DB:-ourhike_test}

BACKEND_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_FILE="$BACKEND_DIR/docker-compose.yml"

have() { command -v "$1" >/dev/null 2>&1; }

log() { echo "[local-postgres] $*"; }

server_is_up() {
  if have pg_isready; then
    pg_isready -h "$PG_HOST" -p "$PG_PORT" >/dev/null 2>&1
  else
    # No client tools on PATH yet (the docker path installs none). A bare TCP
    # connect is a weaker check than pg_isready - it can't tell "accepting
    # connections" from "still recovering" - so it is only the fallback.
    (exec 3<>"/dev/tcp/$PG_HOST/$PG_PORT") >/dev/null 2>&1
  fi
}

wait_for_server() {
  for _ in $(seq 1 30); do
    if server_is_up; then return 0; fi
    sleep 1
  done
  return 1
}

# --- superuser access -------------------------------------------------------
# Creating a role and a database needs a superuser connection, and how you get
# one differs per install: Debian's package authenticates the `postgres` OS
# user by peer, Homebrew makes your own account the superuser, the Docker image
# hands you POSTGRES_USER. Probe once, remember which worked, and fail with the
# candidates listed rather than with whatever the last attempt happened to say.
SUPER_MODE=""

detect_super_mode() {
  local probe="select 1"
  if psql -w -h "$PG_HOST" -p "$PG_PORT" -U postgres -d postgres -tAc "$probe" >/dev/null 2>&1; then
    SUPER_MODE=direct_postgres
  elif psql -w -h "$PG_HOST" -p "$PG_PORT" -d postgres -tAc "$probe" >/dev/null 2>&1; then
    SUPER_MODE=direct_current_user
  elif sudo -n -u postgres psql -w -p "$PG_PORT" -d postgres -tAc "$probe" >/dev/null 2>&1; then
    SUPER_MODE=sudo_postgres
  elif [ "$(id -u)" = "0" ] && su postgres -c "psql -w -p $PG_PORT -d postgres -tAc '$probe'" >/dev/null 2>&1; then
    SUPER_MODE=su_postgres
  else
    return 1
  fi
}

super_psql() {
  local sql=$1
  case "$SUPER_MODE" in
    direct_postgres)
      psql -w -h "$PG_HOST" -p "$PG_PORT" -U postgres -d postgres -v ON_ERROR_STOP=1 -tAc "$sql"
      ;;
    direct_current_user)
      psql -w -h "$PG_HOST" -p "$PG_PORT" -d postgres -v ON_ERROR_STOP=1 -tAc "$sql"
      ;;
    sudo_postgres)
      sudo -n -u postgres psql -w -p "$PG_PORT" -d postgres -v ON_ERROR_STOP=1 -tAc "$sql"
      ;;
    su_postgres)
      su postgres -c "psql -w -p $PG_PORT -d postgres -v ON_ERROR_STOP=1 -tAc \"$sql\""
      ;;
    docker)
      docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -w -U "$PG_USER" -d postgres -v ON_ERROR_STOP=1 -tAc "$sql"
      ;;
    *)
      echo "super_psql called before a superuser connection was established" >&2
      return 1
      ;;
  esac
}

# --- starting a server ------------------------------------------------------

start_native() {
  if server_is_up; then
    log "a server is already listening on $PG_HOST:$PG_PORT"
    return 0
  fi

  if have pg_ctlcluster && have pg_lsclusters; then
    # Debian/Ubuntu: clusters are named `<version> <name>` and started through
    # pg_ctlcluster rather than pg_ctl. Pick the one on our port if there is
    # one, else the first cluster listed.
    local line version cluster
    line=$(pg_lsclusters --no-header 2>/dev/null | awk -v port="$PG_PORT" '$3 == port {print; exit}')
    [ -n "$line" ] || line=$(pg_lsclusters --no-header 2>/dev/null | head -n 1)
    if [ -n "$line" ]; then
      version=$(echo "$line" | awk '{print $1}')
      cluster=$(echo "$line" | awk '{print $2}')
      log "starting cluster $version/$cluster"
      # `start` on an already-running cluster exits non-zero, which is not a
      # failure worth aborting on - the wait below is the real check.
      pg_ctlcluster "$version" "$cluster" start || true
      wait_for_server && return 0
    fi
  fi

  return 1
}

start_docker() {
  have docker || return 1
  docker compose version >/dev/null 2>&1 || {
    log "docker is installed but 'docker compose' is not available"
    return 1
  }

  log "starting the postgres service from $COMPOSE_FILE"
  OURHIKE_PG_PORT="$PG_PORT" OURHIKE_PG_USER="$PG_USER" \
    OURHIKE_PG_PASSWORD="$PG_PASSWORD" OURHIKE_PG_DEV_DB="$DEV_DB" \
    docker compose -f "$COMPOSE_FILE" up -d
  wait_for_server || return 1
  SUPER_MODE=docker
  return 0
}

MODE=${OURHIKE_PG_MODE:-auto}
case "$MODE" in
  native) start_native || { log "could not start a native Postgres"; exit 1; } ;;
  docker) start_docker || { log "could not start Postgres via docker compose"; exit 1; } ;;
  auto)
    start_native || start_docker || {
      cat >&2 <<'EOF'
[local-postgres] No local Postgres could be started.

Install one, or start Docker, then re-run this script:
  Debian/Ubuntu  sudo apt-get install -y postgresql-16
  macOS          brew install postgresql@16 && brew services start postgresql@16
  Windows        winget install PostgreSQL.PostgreSQL.16
  Any of them    start Docker Desktop (this script will use backend/docker-compose.yml)
EOF
      exit 1
    }
    ;;
  *) echo "OURHIKE_PG_MODE must be auto, native or docker (got '$MODE')" >&2; exit 1 ;;
esac

# --- role and databases -----------------------------------------------------

if [ "$SUPER_MODE" != "docker" ]; then
  detect_super_mode || {
    cat >&2 <<EOF
[local-postgres] Postgres is listening on $PG_HOST:$PG_PORT but no superuser
connection worked. Tried, in order:
  psql -U postgres            (Docker image, or a password-less local superuser)
  psql                        (Homebrew, where your own account is the superuser)
  sudo -u postgres psql       (Debian/Ubuntu)
  su postgres -c psql         (Debian/Ubuntu as root)
Create the role and databases by hand if your install differs:
  CREATE ROLE $PG_USER LOGIN PASSWORD '$PG_PASSWORD';
  CREATE DATABASE $DEV_DB OWNER $PG_USER;
  CREATE DATABASE $TEST_DB OWNER $PG_USER;
EOF
    exit 1
  }
fi

role_exists=$(super_psql "select 1 from pg_roles where rolname = '$PG_USER'" | tr -d '[:space:]')
if [ "$role_exists" = "1" ]; then
  log "role $PG_USER already exists"
else
  log "creating role $PG_USER"
  # CREATEDB so the role can make its own scratch databases later without
  # needing this script again; not SUPERUSER, because production's role is not
  # one either and a local setup that quietly allows more than production does
  # is how a migration that needs superuser gets written without anyone
  # noticing.
  super_psql "create role \"$PG_USER\" login createdb password '$PG_PASSWORD'" >/dev/null
fi

for db in "$DEV_DB" "$TEST_DB"; do
  db_exists=$(super_psql "select 1 from pg_database where datname = '$db'" | tr -d '[:space:]')
  if [ "$db_exists" = "1" ]; then
    log "database $db already exists"
  else
    log "creating database $db owned by $PG_USER"
    super_psql "create database \"$db\" owner \"$PG_USER\"" >/dev/null
  fi
done

cat <<EOF
[local-postgres] ready.

  dev   DATABASE_URL=postgresql+psycopg://$PG_USER:$PG_PASSWORD@$PG_HOST:$PG_PORT/$DEV_DB
  test  DATABASE_URL=postgresql+psycopg://$PG_USER:$PG_PASSWORD@$PG_HOST:$PG_PORT/$TEST_DB

Both are what app/config.py and tests/conftest.py already default to, so
nothing needs exporting unless you changed one of the OURHIKE_PG_* variables.
EOF
