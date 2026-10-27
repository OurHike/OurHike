#!/usr/bin/env bash
# The cluster-wide roles a Supabase project has and the steward migration
# grants to (anon, authenticated, service_role, and its own steward_loader),
# on the local Postgres backend/scripts/local-postgres.sh starts. Its login,
# `ourhike`, may not create roles (that script makes it createdb only), so
# this asks the postgres superuser, as that script does, and makes `ourhike`
# a member of each, which is how the tests switch to them. CI's Postgres
# service logs in as a superuser, where the tests create them themselves.
set -euo pipefail

PG_PORT="${OURHIKE_PG_PORT:-5432}"
PG_USER="${OURHIKE_PG_USER:-ourhike}"

sql="
do \$\$
declare r text;
begin
  foreach r in array array['anon', 'authenticated', 'service_role', 'steward_loader'] loop
    if not exists (select from pg_roles where rolname = r) then
      execute format('create role %I nologin', r);
    end if;
    execute format('grant %I to %I', r, '${PG_USER}');
  end loop;
end
\$\$;"

# On stdin, so no shell between here and psql expands the $$ quoting.
if [ "$(id -u)" = "0" ]; then
  printf '%s\n' "${sql}" | su postgres -c "psql -w -p ${PG_PORT} -d postgres -v ON_ERROR_STOP=1 -q"
else
  printf '%s\n' "${sql}" | sudo -u postgres psql -w -p "${PG_PORT}" -d postgres -v ON_ERROR_STOP=1 -q
fi
echo "[steward-db] roles anon, authenticated, service_role, steward_loader ready for ${PG_USER}"
