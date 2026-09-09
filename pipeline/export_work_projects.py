"""Publish volunteer work projects as a static artifact (#760).

features/VOLUNTEERING.md Phase B is the design. The fourth artifact in the
family CONDITIONS_DELIVERY.md established:

    conditions/closures.json        verified OurHike closures
    conditions/reports.json         verified public reports
    conditions/atc_updates.json     the ATC's own notices
    conditions/notes.json           visible field notes
    conditions/work_projects.json   club workdays a hiker can join   (this)

Under `conditions/` for the property that prefix actually means - rewritten
in place, never released immutably (lib/releases.is_release_artifact) - and
this layer needs it more than any: **this is the first data in the app that
EXPIRES.** A workday nine days out is wrong the moment it is cancelled, so
it must never ride an offline package (#760 is explicit), and a cancelled
row must clear with the next bake, which only a rewritten-in-place key does.

THE INPUT IS A REVIEWED FILE IN GIT, exactly as `export_atc_updates.py`
reads `reference/atc_updates.json` and for the same reasons: no database,
no credential, a merged pull request is what releases rows. Refusing is the
normal case, not an error path - an unreviewed file publishes nothing and
exits 0, a reviewed file with a bad row publishes nothing and exits 1.

ONE LIST, EVERY ENVIRONMENT. This exporter used to ask $OURHIKE_DATA_ENV
which environment it was baking for, because the reviewed file's
`ua_sample_rows` published to UA and dev only (maintainer decision
2026-08-20, on #760). Maintainer decision 2026-09-09 retired those rows -
"no invented workday may reach a hiker" is a claim about the map, not about
production's copy of it - so there is nothing left for the environment to
select between, and the question is gone rather than answered. Every
environment's artifact now carries the reviewed `rows` and only those;
lib/work_projects.py refuses the retired key outright.

    python export_work_projects.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.hashing import sha256_file
from lib.manifest_paths import to_manifest_path
from lib.work_projects import file_problems, is_reviewed, published_rows

ROOT = Path(__file__).resolve().parent
REVIEWED_PATH = ROOT / "reference" / "work_projects.json"
OUT_DIR = ROOT / "data" / "processed" / "conditions"
OUT_PATH = OUT_DIR / "work_projects.json"

# Its own manifest, for the reason every conditions exporter has one: each
# rewrites its manifest whole, and sharing a file would make the published
# set depend on which script ran last (see export_atc_updates.py).
MANIFEST_PATH = ROOT / "data" / "processed" / "work_projects_manifest.json"

# The payload name, which becomes `conditions/<name>.json` in the bucket and
# the field the client validates the document by (lib/r2_keys.py on why it
# can never be renamed).
PAYLOAD = "work_projects"


def _stamp_utc(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    if not REVIEWED_PATH.exists():
        print(f"{REVIEWED_PATH} does not exist; publishing nothing.")
        return 0

    document = json.loads(REVIEWED_PATH.read_text())

    if not is_reviewed(document):
        # The honest outcome of "nobody has looked yet" - see the module
        # docstring for why this is 0 and not a red X.
        print(f"{REVIEWED_PATH} has no reviewed_at; publishing nothing.")
        return 0

    problems = file_problems(document)
    if problems:
        for problem in problems:
            print(f"REFUSED: {problem}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    rows = published_rows(document)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "generated_at": _stamp_utc(now),
                # The review's own age rides along, exactly as it does for the
                # ATC notices: a daily bake of a months-old review must not
                # render as fresh (export_atc_updates.py's two-ages argument).
                "reviewed_at": document["reviewed_at"],
                PAYLOAD: rows,
            },
            indent=2,
        )
        + "\n"
    )

    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "artifacts": {
                    PAYLOAD: {
                        "path": to_manifest_path(OUT_PATH),
                        "sha256": sha256_file(OUT_PATH),
                        "count": len(rows),
                        "generated_at": _stamp_utc(now),
                    }
                }
            },
            indent=2,
        )
        + "\n"
    )

    print(f"Wrote {len(rows)} work project(s) to {OUT_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
