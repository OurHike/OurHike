#!/usr/bin/env bash
# The dbt docs site for ourhike.org/data/, built against an empty warehouse.
# action.yml beside this file says why empty, and what was measured.
#
#   build.sh <output dir> [--no-dbt-deps]
#
# Run from the repository root, with the dbt that pipeline/requirements-dbt.txt
# pins first on PATH. --no-dbt-deps is scripts/test.sh's sandbox workaround:
# use pipeline/dbt/dbt_packages/ as it is, because a web session's proxy cannot
# fetch the package tarballs (the dbt skill has the clone commands). The site
# is not checked here; the caller checks the copy it ships, with
# pipeline/check_docs_site.py.
set -euo pipefail

out="${1:?usage: build.sh <output dir> [--no-dbt-deps]}"
deps=true
if [ "${2:-}" = "--no-dbt-deps" ]; then
  deps=false
fi
# Refused rather than cleared: a site left from an earlier build would mix
# into this one, and an `rm -rf` of a path a caller typed is not this script's
# to run.
if [ -e "$out" ]; then
  echo "::error::$out already exists. Give build.sh a directory that is not there yet." >&2
  exit 1
fi

# The empty warehouse, and the writers' directory, outside the checkout: on a
# laptop pipeline/data/ may hold a real fetch, and nothing here may read it.
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
# The documented opt-out and no other switch (pipeline-tests.yml's dbt job
# says why that variable, and why never DBT_SKIP_REMOTE_LICENSE).
export DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false
export OURHIKE_WAREHOUSE="$scratch/warehouse.duckdb"
export OURHIKE_PROCESSED_DIR="$scratch/processed"

cd pipeline/dbt
if $deps; then
  dbt deps --profiles-dir .
else
  echo "dbt deps: skipped (--no-dbt-deps), using pipeline/dbt/dbt_packages/ as it is"
fi
# No --vars, ever: dbt_rt.invocations publishes vars_override with the page.
dbt docs generate --profiles-dir . --output-dir "$out"
echo "docs site: $(find "$out" -type f | wc -l) files in $out"
