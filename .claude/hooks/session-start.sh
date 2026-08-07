#!/bin/bash
# SessionStart hook for Claude Code on the web.
#
# A fresh web container has none of the test suites' dependencies installed,
# and its proxy 403s extensions.duckdb.org - which used to fail every
# spatial-dependent pipeline test, since `INSTALL spatial` downloads the
# extension on first use. PyPI is reachable and DuckDB publishes its
# extensions there, so this installs the bundled build and seeds it where
# `INSTALL spatial` looks before trying the network.
#
# duckdb is pinned to duckdb-extension-spatial's newest release because
# extensions are ABI-locked to the exact DuckDB version. That pin now lives in
# pipeline/requirements.in and is read back out of the compiled
# requirements.txt below, so there is one version to bump rather than two that
# can silently disagree. CI installs the same compiled file and downloads the
# extension from the network like always.
set -euo pipefail

# Local machines have real network access and their own environment - this
# is only for the sandbox.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# The hook runtime provides CLAUDE_PROJECT_DIR; the fallback keeps the
# script runnable by hand from anywhere inside the repo.
cd "${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

DUCKDB_PIN=$(sed -n 's/^duckdb==\([^ ;]*\).*/\1/p' pipeline/requirements.txt | head -1)
if [ -z "${DUCKDB_PIN}" ]; then
  echo "[session-start] no duckdb pin found in pipeline/requirements.txt" >&2
  exit 1
fi

# The image ships these five as Debian dist-packages with no RECORD file, so
# pip cannot uninstall them to put a pinned version in their place - it aborts
# the entire install with "Cannot uninstall X, RECORD file not found". They
# were invisible while the requirements were unpinned, because any version
# satisfied a bare requirement. Installing them first with --ignore-installed
# writes the pinned build into site-packages, which precedes dist-packages on
# sys.path, and the -r install that follows is then already satisfied.
#
# This also retires the old cffi workaround: the reason moto's mock_aws used
# to panic was Debian's cryptography 41 missing _cffi_backend, and a pinned
# cryptography from PyPI is a wheel that bundles its own.
#
# CI never reaches any of this - setup-python starts from a clean interpreter.
DEBIAN_SHADOWED="PyYAML cryptography pyjwt pyparsing packaging"

# Pinned install that survives the above. $1 is the compiled requirements
# file, which doubles as the constraint so the shadow copies land on exactly
# the versions that file pins; any remaining arguments are installed with it.
pip_install_pinned() {
  local reqs="$1"
  shift
  pip install -q --ignore-installed -c "${reqs}" ${DEBIAN_SHADOWED}
  pip install -q -r "${reqs}" "$@"
}

echo "[session-start] pipeline deps, duckdb pinned to ${DUCKDB_PIN}"
# duckdb itself is already pinned by the compiled file; only the extension
# needs naming here, and it must match that pin exactly.
pip_install_pinned pipeline/requirements-dev.txt \
  "duckdb-extension-spatial==${DUCKDB_PIN}"

echo "[session-start] backend deps"
pip_install_pinned backend/requirements-dev.txt

echo "[session-start] local postgres for the backend"
# The backend's database is Supabase's Postgres, so its tests run against a
# real Postgres - not an embedded stand-in. The web container ships Postgres 16
# with the cluster stopped, which is one command away from usable; the script
# starts it and creates the role and the dev/test databases. Without this, the
# whole backend suite fails on connection refused.
#
# Not fatal if it can't: every other suite in this repository runs without a
# database, and a hook that aborts here would take them down too.
bash backend/scripts/local-postgres.sh || \
  echo "[session-start] WARNING: no local postgres - backend tests will not run"

echo "[session-start] repository-settings test deps"
# Through the same helper as the other two: this suite pins PyYAML, which is
# one of the Debian-shadowed five. It happens to work today only because the
# pipeline install already shadowed it, and that is not a thing to depend on.
pip_install_pinned .github/tests/requirements-dev.txt

echo "[session-start] seeding the duckdb spatial extension"
python - <<'PY'
"""Copy the PyPI-bundled spatial extension to where INSTALL looks.

DuckDB treats an already-installed extension as satisfying INSTALL, so
seeding ~/.duckdb/extensions means the tests' `INSTALL spatial; LOAD
spatial;` never reaches the blocked network.
"""
import pathlib
import shutil
from importlib.metadata import distribution

import duckdb

dist = distribution("duckdb-extension-spatial")
src = next(
    pathlib.Path(dist.locate_file(f))
    for f in dist.files
    if f.name == "spatial.duckdb_extension"
)
platform = duckdb.connect().execute("PRAGMA platform").fetchone()[0]
dest = (
    pathlib.Path.home()
    / ".duckdb/extensions"
    / f"v{duckdb.__version__}"
    / platform
    / src.name
)
if not dest.exists() or dest.stat().st_size != src.stat().st_size:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)

con = duckdb.connect()
con.execute("INSTALL spatial; LOAD spatial;")
con.execute("SELECT ST_Point(0, 0)")
print(f"spatial loads offline for duckdb {duckdb.__version__}")
PY

echo "[session-start] client deps"
(cd client && npm install --no-audit --no-fund)

echo "[session-start] ready"
