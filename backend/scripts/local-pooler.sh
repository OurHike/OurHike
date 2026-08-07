#!/usr/bin/env bash
# Put a transaction-mode connection pooler in front of the local test database.
#
# Supabase's dashboard offers a pooled connection string first (port 6543,
# Supavisor in transaction mode), and connecting through one changes what a
# client may assume: a transaction can land on a different Postgres backend
# each time, so anything a driver leaves on a connection between transactions
# is gone. psycopg's automatic prepared statements are exactly that, and the
# resulting 500 appears only in production, only once a query is warm.
#
# pgbouncer in transaction mode is that behaviour, locally: not the same
# software as Supavisor, but the same constraint, which is the part worth
# testing against. `max_prepared_statements = 0` keeps it that way - newer
# pgbouncer can emulate prepared statements across backends, and turning that
# on would quietly make the test prove nothing.
#
# Prints the URL to export as POOLER_DATABASE_URL; tests/test_pooler.py skips
# itself when that is unset.
set -euo pipefail

PG_HOST=${OURHIKE_PG_HOST:-127.0.0.1}
PG_PORT=${OURHIKE_PG_PORT:-5432}
PG_USER=${OURHIKE_PG_USER:-ourhike}
PG_PASSWORD=${OURHIKE_PG_PASSWORD:-ourhike}
TEST_DB=${OURHIKE_PG_TEST_DB:-ourhike_test}
POOLER_PORT=${OURHIKE_POOLER_PORT:-6432}

# Not under the repository and not under /tmp's per-session sandbox: pgbouncer
# refuses to run as root and drops to an unprivileged user, which then has to
# be able to read its own config. A world-readable directory it owns avoids a
# permission failure that reads like a configuration error.
RUN_DIR=${OURHIKE_POOLER_DIR:-/var/tmp/ourhike-pgbouncer}

log() { echo "[local-pooler] $*"; }

command -v pgbouncer >/dev/null 2>&1 || {
  cat >&2 <<'EOF'
[local-pooler] pgbouncer is not installed.

  Debian/Ubuntu  sudo apt-get install -y pgbouncer
  macOS          brew install pgbouncer

Without it the pooler test skips - it does not fail. Nothing else in the
suite needs this.
EOF
  exit 1
}

# A real query through the pooler, not a port check. Debian's pgbouncer
# package starts its own service on this port at install time, with a config
# that routes nothing - so "something is listening" and "our database is
# reachable" are genuinely different questions here, and answering the easy
# one would hand the tests a pooler that fails every connection.
pooler_serves_our_database() {
  # PGCONNECT_TIMEOUT because psql waits indefinitely by default: a socket
  # that accepts the connection and then never answers the startup packet
  # would hang this script rather than failing it.
  PGPASSWORD="$PG_PASSWORD" PGCONNECT_TIMEOUT=5 \
    psql -w -h "$PG_HOST" -p "$POOLER_PORT" -U "$PG_USER" \
    -d "$TEST_DB" -tAc "select 1" >/dev/null 2>&1
}

port_is_taken() {
  (exec 3<>"/dev/tcp/$PG_HOST/$POOLER_PORT") >/dev/null 2>&1
}

if pooler_serves_our_database; then
  log "a pooler serving $TEST_DB is already listening on $PG_HOST:$POOLER_PORT"
else
  if port_is_taken; then
    cat >&2 <<EOF
[local-pooler] $PG_HOST:$POOLER_PORT is in use by something that will not
serve $TEST_DB - most likely the pgbouncer system service the Debian package
starts on install, whose default config routes no databases.

  sudo systemctl stop pgbouncer      # then re-run this script
  OURHIKE_POOLER_PORT=6433 $0        # or put ours somewhere else
EOF
    exit 1
  fi

  mkdir -p "$RUN_DIR"

  cat > "$RUN_DIR/pgbouncer.ini" <<EOF
[databases]
$TEST_DB = host=$PG_HOST port=$PG_PORT dbname=$TEST_DB

[pgbouncer]
listen_addr = $PG_HOST
listen_port = $POOLER_PORT
auth_type = trust
auth_file = $RUN_DIR/userlist.txt
pool_mode = transaction
max_client_conn = 50
# Small on purpose: fewer server backends means transactions get shuffled
# across them sooner, which is the condition under test rather than an
# incidental detail.
default_pool_size = 2
# See the header - emulation here would hide the very failure this exists to
# catch.
max_prepared_statements = 0
logfile = $RUN_DIR/pgbouncer.log
pidfile = $RUN_DIR/pgbouncer.pid
EOF

  printf '"%s" "%s"\n' "$PG_USER" "$PG_PASSWORD" > "$RUN_DIR/userlist.txt"
  chmod -R a+rX "$RUN_DIR"

  log "starting pgbouncer in transaction mode on $PG_HOST:$POOLER_PORT"
  if [ "$(id -u)" = "0" ]; then
    # pgbouncer exits with "PgBouncer should not run as root". Run it as the
    # postgres user, which exists wherever a Postgres server does.
    chown -R postgres "$RUN_DIR"
    su postgres -c "pgbouncer -d $RUN_DIR/pgbouncer.ini"
  else
    pgbouncer -d "$RUN_DIR/pgbouncer.ini"
  fi

  for _ in $(seq 1 20); do
    pooler_serves_our_database && break
    sleep 1
  done
  pooler_serves_our_database || {
    log "pgbouncer came up but $TEST_DB is not reachable through it"
    log "see $RUN_DIR/pgbouncer.log"
    exit 1
  }
fi

cat <<EOF
[local-pooler] ready.

  POOLER_DATABASE_URL=postgresql+psycopg://$PG_USER:$PG_PASSWORD@$PG_HOST:$POOLER_PORT/$TEST_DB

Export that and tests/test_pooler.py runs instead of skipping.
EOF
