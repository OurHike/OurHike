#!/usr/bin/env bash
# The dbt docs site for ourhike.org/data/, built against an empty warehouse.
# action.yml beside this file says why empty, and what was measured.
#
#   build.sh <output dir> [--no-dbt-deps]
#
# Run from the repository root, with pipeline/requirements-dbt.txt's dbt first
# on PATH, after pipeline/generate_dbt.py has written the generated models
# (decision 91; action.yml's step before this one), and Node and npm for
# DuckDB-WASM below. --no-dbt-deps (scripts/test.sh's sandbox workaround) uses
# pipeline/dbt/dbt_packages/ as it is, because a web session's proxy cannot
# fetch the package tarballs (the dbt skill has the clone commands). The
# caller checks the copy it ships, with pipeline/check_docs_site.py --served.
set -euo pipefail

out="${1:?usage: build.sh <output dir> [--no-dbt-deps]}"
deps=true
if [ "${2:-}" = "--no-dbt-deps" ]; then
  deps=false
fi
# Refused rather than cleared: an earlier build's files would mix into this
# one, and this script will not `rm -rf` a path a caller typed.
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

# DuckDB-WASM, served at /data/duckdb/ from our own site and never from a CDN
# (pipeline/ELT.md decision 93, SEC-1 of PR #1805's second review): the page
# runs on ourhike.org's origin, where a signed-in hiker's session is kept, so
# any script it loads can read that session. duckdb-wasm/loader.js says why
# the files are laid out as they are, and what was measured.
# - The npm packages as duckdb-wasm/package-lock.json pins them: npm ci checks
#   every tarball against the lockfile's sha512 `integrity`, and runs no
#   install script. Installed under the scratch directory, not the checkout.
# - The parquet extension the page's first query loads, which no npm package
#   carries: fetched from DuckDB's own repository by the exact paths in
#   duckdb-wasm/extensions.sha256, and refused unless every file has the
#   sha256 written beside it there. DuckDB checks the extension's own
#   signature again when it loads it (loader.js has the measurement).
# Staged before dbt runs, so a refused download fails in seconds.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
npm_dir="$scratch/duckdb-npm"
duckdb_dir="$scratch/duckdb"
mkdir -p "$npm_dir"
cp "$here/duckdb-wasm/package.json" "$here/duckdb-wasm/package-lock.json" "$here/duckdb-wasm/loader.js" "$npm_dir/"
npm ci --prefix "$npm_dir" --ignore-scripts --no-audit --no-fund
node "$here/duckdb-wasm/stage.mjs" "$npm_dir" "$duckdb_dir"
user_agent="$(cd pipeline && python -c 'from lib.user_agent import USER_AGENT; print(USER_AGENT)')"
while read -r _sha256 path; do
  mkdir -p "$duckdb_dir/extensions/$(dirname "$path")"
  curl -fsS --retry 3 --max-time 120 -A "$user_agent" \
    -o "$duckdb_dir/extensions/$path" "https://extensions.duckdb.org/$path"
done < "$here/duckdb-wasm/extensions.sha256"
(cd "$duckdb_dir/extensions" && sha256sum --check --strict "$here/duckdb-wasm/extensions.sha256")
printf '\n%s\n' "extensions/: DuckDB's own extensions (MIT, https://github.com/duckdb/duckdb), from https://extensions.duckdb.org" \
  >> "$duckdb_dir/LICENSES.txt"

cd pipeline/dbt
if $deps; then
  dbt deps --profiles-dir .
else
  echo "dbt deps: skipped (--no-dbt-deps), using pipeline/dbt/dbt_packages/ as it is"
fi
# No --vars, ever: dbt_rt.invocations publishes vars_override with the page.
# The base's trailing `?` is deliberate: duckdb-wasm/loader.js says why.
dbt docs generate --profiles-dir . --output-dir "$out" --duckdb-cdn-base "/data/duckdb/duckdb.js?"
if [ -e "$out/duckdb" ]; then
  echo "::error::dbt wrote $out/duckdb, the path DuckDB-WASM is served from. Move one of them." >&2
  exit 1
fi
cp -r "$duckdb_dir" "$out/duckdb"
echo "docs site: $(find "$out" -type f | wc -l) files in $out, $(find "$out/duckdb" -type f | wc -l) of them DuckDB-WASM's"
