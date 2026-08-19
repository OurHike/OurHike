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

# WHICH INTERPRETER TO INSTALL INTO, and why this is not just `pip` (#822).
#
# This script used to call bare `pip` and `python`, which on the web image are
# Debian's 3.11. `pipeline/requirements.txt` pins `numpy==2.5.2`, and numpy
# 2.5 requires Python >= 3.12 - so the very first pinned install died with
# "No matching distribution found for numpy==2.5.2". `set -euo pipefail` meant
# the run ended there, before the dev requirements that carry pytest, so every
# web session had NO pytest for any of the three suites and nothing said so.
# That is the second time this hook has silently provisioned nothing; see
# pip_install_pinned's comment for the first.
#
# Chosen rather than hardcoded, because both obvious constants are wrong within
# one image update: naming `python3.13` breaks when the image ships 3.14 or
# drops 3.13, and naming CI's version breaks whenever the image does not have
# it. So: prefer the version CI actually uses, read out of the workflow rather
# than copied (one home for it), and otherwise take the newest interpreter
# present. Newest, not `python3` - the whole failure was that `python3` is the
# oldest thing installed.
#
# There is no floor test here on purpose. If the chosen interpreter cannot
# satisfy the pins, pip says so by name and the gate at the end of this script
# fails loudly - which is better than a floor that has to be kept in step with
# whatever the lockfiles currently need.
ci_python_version() {
  sed -n 's/^[[:space:]]*python-version:[[:space:]]*"\([0-9][0-9.]*\)".*/\1/p' \
    .github/workflows/pipeline-tests.yml | head -1
}

available_pythons() {
  # Real interpreters only - `ls python3.*` also matches python3.11-config.
  ls -1 /usr/local/bin/python3.* /usr/bin/python3.* 2>/dev/null \
    | grep -E '/python3\.[0-9]+$' \
    | xargs -r -n1 basename \
    | sort -u -t. -k2 -n -r
}

pick_python() {
  local ci
  ci="$(ci_python_version)"
  local candidate
  for candidate in ${ci:+"python${ci}"} $(available_pythons); do
    if command -v "${candidate}" >/dev/null 2>&1; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

PY="$(pick_python)" || {
  echo "[session-start] no python3.N interpreter found on PATH" >&2
  exit 1
}
echo "[session-start] installing with ${PY} ($(${PY} --version 2>&1)); CI uses $(ci_python_version)"

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
#
# The constraint is a copy with extras stripped, not the file itself: pip
# rejects a constraints file containing `coverage[toml]` or `moto[s3]` with
# "ERROR: Constraints cannot have extras" and installs nothing at all. Those
# two entered pipeline/requirements-dev.txt when the dependencies were pinned,
# and every web session since has provisioned no Python dependencies for any
# of the three suites. Extras only select optional dependencies - dropping
# them costs the constraint nothing, because a constraint pins a version and
# never asks for a package to be installed.
pip_install_pinned() {
  local reqs="$1"
  shift
  local constraints
  constraints="$(mktemp)"
  sed 's/\[[^][]*\]//g' "${reqs}" >"${constraints}"
  "${PY}" -m pip install -q --ignore-installed -c "${constraints}" ${DEBIAN_SHADOWED}
  rm -f "${constraints}"
  "${PY}" -m pip install -q -r "${reqs}" "$@"
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
"${PY}" - <<'PY'
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

# THE GATE: prove what this script claims, or fail saying which part is missing.
#
# Both times this hook silently provisioned nothing (#822 and the
# extras-in-a-constraints-file bug pip_install_pinned describes), the symptom
# reached a session as "No module named pytest" during unrelated work, hours
# later, and read like a broken container rather than a broken hook. A hook
# that cannot say whether it worked will have a third.
#
# Checked here rather than trusted: `set -e` only proves each command exited 0,
# and the extras bug exited 0 while installing nothing at all.
#
# One representative import per suite - enough to tell "this suite can run"
# from "this suite has nothing", which is the distinction both outages blurred.
# Not a substitute for running the suites, and not trying to be.
echo "[session-start] verifying the suites can actually run"
gate_failed=0
gate_check() {
  local label="$1" module="$2"
  if "${PY}" -c "import ${module}" >/dev/null 2>&1; then
    echo "  ok    ${label} (${module})"
  else
    echo "  FAIL  ${label}: ${PY} cannot import ${module}" >&2
    gate_failed=1
  fi
}

gate_check "test runner"       pytest
gate_check "pipeline"          duckdb
gate_check "backend"           fastapi
gate_check "repo settings"     yaml

if [ "${gate_failed}" -ne 0 ]; then
  echo "[session-start] FAILED: dependencies are missing - the suites will not run." >&2
  echo "[session-start] Interpreter was ${PY} ($(${PY} --version 2>&1))." >&2
  exit 1
fi
echo "[session-start] ready: ${PY} can run all three Python suites"

echo "[session-start] ready"
