"""Publish the ATC's own Trail Updates as a static artifact (#460).

[features/ATC_TRAIL_UPDATES.md](../features/ATC_TRAIL_UPDATES.md) is the
design. The third artifact in the family
[CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md) established:

    conditions/closures.json        verified OurHike closures
    conditions/reports.json         verified public reports
    conditions/atc_updates.json     the ATC's own notices          (this)

THE INPUT IS A FILE IN GIT, NOT A DATABASE AND NOT A LIVE PARSE, which is the
one structural difference from `export_conditions.py` and the reason this is
a separate script rather than a fourth query in that one. ATC updates
deliberately never reach `public.closures`: `reported_by` is
`nullable=False`, an ATC notice has no reporter, and the synthetic-profile
workaround is refused by the design because it would put a fictional person
in the identity table and imply somebody accepted responsibility for a claim
they never made. So there is no backend change here, no migration, and no new
credential - only `reference/atc_updates.json`, which a person edits and a
merged pull request releases.

TWO AGES, AND THE ONE A HIKER CARES ABOUT IS NOT OURS. Every artifact in this
family carries `generated_at` - when the bake ran - and the client renders it
as "as of X". That is not enough here. The bake runs daily; the *review* it
bakes might be months old, and a daily `generated_at` on a stale review would
claim a freshness nobody has. So the artifact carries `reviewed_at` as well,
straight from the reviewed file, and the client renders that. Each row then
carries a third: ATC's own `updated_at`, which is the age of the notice
itself and the most important of the three.

    generated_at   when this script ran
    reviewed_at    when a person last checked the file against ATC's page
    updated_at     when ATC last edited that notice          (per row)

REFUSING IS THE NORMAL CASE, NOT AN ERROR PATH. An unreviewed file publishes
nothing: no artifact, no manifest, nothing for `publish.py` to upload, and a
client that reads a 404 and shows no ATC layer at all. That is the honest
outcome of "nobody has looked yet", and it is why this exits 0 while writing
nothing - a red X on a job that is behaving correctly is how a real failure
gets missed later.

A file that IS reviewed but has a bad row is the opposite: that is a failure,
it exits non-zero, and it publishes nothing rather than a partial set. Same
stance as `export_conditions.py`'s `assert_reader_permissions`, for the same
reason - a missing closure is invisible, so half a set of safety notices is
worse than none.

    python export_atc_updates.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from lib.atc_updates import file_problems, is_reviewed, published_rows

ROOT = Path(__file__).resolve().parent
REVIEWED_PATH = ROOT / "reference" / "atc_updates.json"
OUT_DIR = ROOT / "data" / "processed" / "conditions"
OUT_PATH = OUT_DIR / "atc_updates.json"

# Its own manifest rather than a fourth entry in `conditions_manifest.json`.
# Two scripts writing one file would make the published set depend on which
# ran last: `export_conditions.py` rewrites that manifest whole, so a run
# where it went second would drop this artifact from the upload with nothing
# said. publish.py reads both (see its `conditions/` block).
MANIFEST_PATH = ROOT / "data" / "processed" / "atc_updates_manifest.json"

# The payload name, which becomes `conditions/<name>.json` in the bucket and
# the field the client validates the document by. A key in that bucket is a
# URL deployed clients already request and can never be renamed
# (lib/r2_keys.py), so it is spelled once, here.
PAYLOAD = "atc_updates"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _stamp_utc(value: datetime) -> str:
    """The same `...Z` stamping export_conditions.py uses, for the same
    reason: a naive timestamp is read as *local* by `new Date()`, which moves
    every date a hiker reads by their own offset."""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_document(document: dict, generated_at: datetime) -> dict:
    """The artifact, from the reviewed file.

    `reviewed_at` rides at the top level rather than on each row because it
    is a fact about the review, not about any one notice: a reviewer checks
    the page, not a row. `updated_at` stays per row because ATC edits each
    notice on its own clock.
    """
    return {
        "generated_at": _stamp_utc(generated_at),
        "reviewed_at": document["reviewed_at"],
        PAYLOAD: published_rows(document),
    }


def main() -> dict | None:
    document = json.loads(REVIEWED_PATH.read_text())

    if not is_reviewed(document):
        # Not a failure. See the module docstring: an unreviewed file is a
        # true statement about where this feature has got to, and the client
        # renders its absence as "no ATC layer" rather than as "the trail is
        # clear according to ATC".
        print(
            f"{REVIEWED_PATH.name} has no `reviewed_at`, so nobody has yet checked it against "
            "ATC's page. Nothing published - an empty artifact would read as 'ATC reports "
            "nothing', which is a different claim from 'we have not looked'. "
            "See features/ATC_TRAIL_UPDATES.md."
        )
        return None

    problems = file_problems(document)
    if problems:
        raise SystemExit(
            f"{REVIEWED_PATH} is reviewed but not publishable, so nothing was written:\n"
            + "\n".join(f"  - {problem}" for problem in problems)
            + "\n\nEvery row has to be right before any of them ships: a dropped closure is "
            "invisible on the map, so a partial set is worse than none."
        )

    generated_at = datetime.now(timezone.utc)
    rows = published_rows(document)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(build_document(document, generated_at), indent=2) + "\n")

    manifest = {
        "artifacts": {
            PAYLOAD: {
                "path": str(OUT_PATH),
                "sha256": sha256_file(OUT_PATH),
                "count": len(rows),
                "generated_at": _stamp_utc(generated_at),
                "reviewed_at": document["reviewed_at"],
            }
        }
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Wrote {len(rows)} ATC update(s) to {OUT_PATH}, reviewed {document['reviewed_at']}.")
    return manifest


if __name__ == "__main__":
    main()
