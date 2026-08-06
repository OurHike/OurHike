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
# extensions are ABI-locked to the exact DuckDB version. Bump the two
# together, and only once PyPI has the matching extension build. CI is
# unaffected either way: it installs requirements-dev.txt unpinned and
# downloads the extension from the network like always.
set -euo pipefail

# Local machines have real network access and their own environment - this
# is only for the sandbox.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# The hook runtime provides CLAUDE_PROJECT_DIR; the fallback keeps the
# script runnable by hand from anywhere inside the repo.
cd "${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

DUCKDB_PIN=1.5.4

echo "[session-start] pipeline deps, duckdb pinned to ${DUCKDB_PIN}"
# cffi rides along because the image's Debian-built cryptography package is
# missing _cffi_backend, which makes moto's mock_aws (and anything else that
# imports cryptography) panic. One pip resolve, so an unpinned duckdb is
# never installed first and then downgraded.
pip install -q -r pipeline/requirements-dev.txt cffi \
  "duckdb==${DUCKDB_PIN}" "duckdb-extension-spatial==${DUCKDB_PIN}"

echo "[session-start] backend deps"
# After the pipeline install, so backend's unpinned duckdb requirement is
# already satisfied by the pin instead of pulling a newer one.
pip install -q -r backend/requirements-dev.txt

echo "[session-start] repository-settings test deps"
pip install -q -r .github/tests/requirements-dev.txt

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
