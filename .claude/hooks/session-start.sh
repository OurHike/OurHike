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
# The selection itself lives in scripts/pick_python.sh - one home, shared
# with scripts/test.sh and scripts/threads.sh, because the install side and
# the run side deciding differently is exactly #859: this hook installed into
# 3.13 while test.sh shelled out to bare `python`, Debian's 3.11, and died on
# "No module named ruff". The reasoning for how pick_python chooses (CI's
# version read from the workflow, else the newest interpreter present) moved
# there with the code.
. scripts/pick_python.sh

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
# ONE HOME, shared with pipeline-tests.yml (#321). This was an inline heredoc
# here until CI needed the same thing; the script says why three copies of it
# would have drifted on the next duckdb bump. It verifies rather than reports,
# so a seeding that silently landed in the wrong path fails here.
"${PY}" pipeline/seed_spatial_extension.py

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
