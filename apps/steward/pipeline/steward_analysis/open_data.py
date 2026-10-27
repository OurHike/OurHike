"""The volunteer work as open files beside sites.json (apps/steward/PLAN.md,
decided 2026-10-27: "the volunteer work is also published as open files").

    python -m steward_analysis.open_data --out ../web/public/data/work

Reads the `steward` schema's three open views through Supabase's REST API with
the project's public anon key, which is exactly what anyone can read, and
writes each as CSV and as Parquet:

    claims    every claim: its site, state and dates; names only on verified work
    photos    the before and after photos of verified work, with their addresses
    weights   every club's ranking-weight changes

plus manifest.json saying when and how many. Nothing here can read more than
the public can: the views are the whole of what the anon key reaches
(apps/steward/db/migrations/0001_steward.sql).

SUPABASE_URL and SUPABASE_ANON_KEY name the project. With either unset, or a
project that does not serve the steward schema yet, this writes nothing and
says so, and exits 0: the app does not depend on these files.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import requests

#: Rows per request. Supabase's API answers at most 1,000 by default.
PAGE = 1000
TIMEOUT = 30

#: view -> (file name, order), oldest first so a file reads as a history.
VIEWS = {
    "open_claims": ("claims", "claimed_at.asc,id.asc"),
    "open_photos": ("photos", "created_at.asc,path.asc"),
    "open_weights": ("weights", "changed_at.asc,id.asc"),
}

#: Each view's columns, in order: an empty view answers with no names, and a
#: file should still say what it would hold. apps/steward/db/tests holds these
#: equal to the views.
VIEW_COLUMNS = {
    "open_claims": [
        "id",
        "rims_id",
        "state",
        "claimed_at",
        "due_at",
        "submitted_at",
        "verified_at",
        "released_at",
        "crew_size",
        "claimer",
        "verified_by",
        "steps_done",
        "verified_hours",
    ],
    "open_photos": ["claim_id", "rims_id", "phase", "point", "path", "created_at"],
    "open_weights": [
        "id",
        "club",
        "deficit",
        "water",
        "trail",
        "cluster",
        "restricted",
        "note",
        "restored_from",
        "changed_by",
        "changed_at",
    ],
}

#: A cell a spreadsheet would run as a formula: the app's CSV export guards
#: against the same (web/src/filters.ts FORMULA_START; the review's finding 12).
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


class NotServed(RuntimeError):
    """The project does not serve the steward schema (yet)."""


def read_view(session: requests.Session, url: str, key: str, view: str, order: str) -> list[dict]:
    rows: list[dict] = []
    while True:
        response = session.get(
            f"{url.rstrip('/')}/rest/v1/{view}",
            params={"select": "*", "order": order, "limit": PAGE, "offset": len(rows)},
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept-Profile": "steward"},
            timeout=TIMEOUT,
        )
        if response.status_code in (404, 406) or (response.status_code == 400 and "PGRST106" in response.text):
            raise NotServed(f"{view}: {response.status_code} {response.text[:200]}")
        response.raise_for_status()
        page = response.json()
        rows.extend(page)
        if len(page) < PAGE:
            return rows


def neutralise(value: object) -> object:
    if isinstance(value, str) and value.startswith(FORMULA_START):
        return "'" + value
    return value


def write(frame: pd.DataFrame, out: Path, name: str) -> None:
    flat = frame.copy().astype(object)
    for column in flat.columns:
        flat[column] = flat[column].map(lambda v: "; ".join(map(str, v)) if isinstance(v, list) else v).map(neutralise)
    flat.to_csv(out / f"{name}.csv", index=False)
    duckdb.from_df(frame).write_parquet(str(out / f"{name}.parquet"))


def export(url: str, key: str, out: Path, session: requests.Session | None = None) -> dict:
    session = session or requests.Session()
    tables = {view: read_view(session, url, key, view, order) for view, (_, order) in VIEWS.items()}
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for view, (name, _) in VIEWS.items():
        frame = pd.DataFrame(tables[view], columns=VIEW_COLUMNS[view])
        if name == "photos":
            frame["url"] = [f"{url.rstrip('/')}/storage/v1/object/public/steward-photos/{p}" for p in frame["path"]]
        write(frame, out, name)
        counts[name] = len(frame)
    manifest = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "source": url, "rows": counts}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    url, key = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        print("open data: SUPABASE_URL or SUPABASE_ANON_KEY is unset; nothing written")
        return 0
    try:
        manifest = export(url, key, args.out)
    except NotServed as exc:
        print(f"open data: the project does not serve the steward schema yet ({exc}); nothing written")
        return 0
    except requests.RequestException as exc:
        print(f"open data: could not read the project ({exc}); nothing written", file=sys.stderr)
        return 0
    print(f"open data: {manifest['rows']} written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
