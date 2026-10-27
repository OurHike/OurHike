"""Loads the analysis's sites into steward.site, which every claim is checked
against and every club's weights are checked against.

    STEWARD_SITES_DATABASE_URL=postgresql://... python -m steward_db.load_sites path/to/sites.json

Run by the daily analysis job after it scores, logged in as a role that may
do nothing but call steward.load_sites() (README.md, "Give the loader a
login"). The address is read from the environment, never the command line,
where it would sit in the process list with its password in it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

DATABASE_URL = "STEWARD_SITES_DATABASE_URL"


def load(database_url: str, sites_json: Path) -> int:
    records = json.loads(sites_json.read_text())
    slim = [
        {"rims_id": r.get("rims_id"), "club": r.get("club"), "action": r.get("action")} for r in records if isinstance(r, dict)
    ]
    with psycopg.connect(database_url) as connection:
        return connection.execute("select steward.load_sites(%s)", (Jsonb(slim),)).fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sites_json", type=Path)
    args = parser.parse_args(argv)
    database_url = os.environ.get(DATABASE_URL, "")
    if not database_url:
        print(f"stopped: set {DATABASE_URL} to the loader's login", file=sys.stderr)
        return 1
    try:
        loaded = load(database_url, args.sites_json)
    except psycopg.Error as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        return 1
    print(f"loaded {loaded} sites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
