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

import json
from datetime import datetime, timezone
from pathlib import Path

from lib.atc_scrape import MileReference, ParsedUpdate
from lib.atc_updates import auto_publish_refusal, auto_row, file_problems, is_reviewed, published_rows
from lib.hashing import sha256_file

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

#: What `fetch_atc_updates.py` left behind, if it has run. Optional on
#: purpose: this script's job is to publish the reviewed rows, and it did that
#: before #963 existed. A missing or unreadable cache costs the auto-published
#: rows and nothing else - it must never cost the reviewed ones, because the
#: reviewed ones are the set a person stood behind.
CACHE_PATH = ROOT / "data" / "raw" / "atc_updates.json"

# The payload name, which becomes `conditions/<name>.json` in the bucket and
# the field the client validates the document by. A key in that bucket is a
# URL deployed clients already request and can never be renamed
# (lib/r2_keys.py), so it is spelled once, here.
PAYLOAD = "atc_updates"


def _stamp_utc(value: datetime) -> str:
    """The same `...Z` stamping export_conditions.py uses, for the same
    reason: a naive timestamp is read as *local* by `new Date()`, which moves
    every date a hiker reads by their own offset."""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def cached_updates(path: Path | None = None) -> list[ParsedUpdate]:
    """What `fetch_atc_updates.py` last read off ATC's site, rehydrated.

    An unreadable cache answers an empty list rather than raising. The
    reviewed rows are what a person stood behind and they publish either way;
    losing the automatic ones to a bad cache is a smaller failure than losing
    the whole artifact to one.
    """
    # Resolved here rather than in the signature: a default bound at
    # definition time captures the real path forever, which is invisible
    # until a test points CACHE_PATH somewhere else and is ignored.
    path = path or CACHE_PATH
    try:
        document = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    entries = document.get("updates")
    if not isinstance(entries, dict):
        return []

    parsed = []
    for slug, entry in entries.items():
        if not isinstance(entry, dict) or not entry.get("listed", True):
            # Dropped from ATC's listing since it was cached. Kept on disk
            # (fetch_atc_updates.py says why) but not republished: we can no
            # longer see it, which is not the same as knowing it is over, and
            # the conservative reading of an invisible notice is to stop
            # asserting it rather than to keep asserting it forever.
            continue
        parsed.append(
            ParsedUpdate(
                slug=slug,
                title=entry.get("title") or "",
                category=entry.get("category"),
                states=list(entry.get("states") or []),
                date_modified=entry.get("date_modified"),
                date_published=entry.get("date_published"),
                miles=[
                    MileReference(
                        direction=m.get("direction", ""),
                        start=m.get("start"),
                        end=m.get("end"),
                        raw=m.get("raw", ""),
                    )
                    for m in entry.get("miles") or []
                ],
                text=entry.get("text") or "",
            )
        )
    return parsed


def automatic_rows(document: dict, parsed: list[ParsedUpdate]) -> tuple[list[dict], list[str]]:
    """The rows ATC has posted since the review that may publish unreviewed.

    Returns the rows and one line per refusal, so the job log says what it
    skipped and why. A silent cap reads as "covered everything" when it did
    not, and this one caps hard on purpose.
    """
    reviewed_ids = {row["atc_id"] for row in document["updates"]}
    reviewed_at = document["reviewed_at"]

    rows, refusals = [], []
    for update in sorted(parsed, key=lambda u: u.slug):
        refusal = auto_publish_refusal(update, reviewed_ids, reviewed_at)
        if refusal is None:
            rows.append(auto_row(update))
            continue
        # Only the ones a person could act on are worth a line. The other two
        # reasons are the steady state - every reviewed row and every notice
        # older than the review is refused on every run - and printing all 89
        # of those hourly would bury the handful that mean something.
        if not (refusal.startswith("already reviewed") or refusal.startswith("last edited")):
            refusals.append(f"{update.slug}: {refusal}")
    return rows, refusals


def build_document(document: dict, generated_at: datetime, automatic: list[dict]) -> dict:
    """The artifact: the reviewed rows, then anything newer nobody has read.

    `reviewed_at` rides at the top level rather than on each row because it
    is a fact about the review, not about any one notice: a reviewer checks
    the page, not a row. `updated_at` stays per row because ATC edits each
    notice on its own clock.

    The two kinds are in ONE payload rather than two, so a client that reads
    this artifact cannot accidentally read only half of it. They are told
    apart by `review_state` on each row, which is what lets the app say ATC
    posted this and nobody here has checked it - and `auto_row` has already
    forced `obstructs_trail` false on every automatic one, so an unread notice
    can never draw a barrier across the treadway.
    """
    return {
        "generated_at": _stamp_utc(generated_at),
        "reviewed_at": document["reviewed_at"],
        PAYLOAD: [*published_rows(document), *automatic],
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
    automatic, refusals = automatic_rows(document, cached_updates())
    rows = [*published_rows(document), *automatic]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(build_document(document, generated_at, automatic), indent=2) + "\n")

    manifest = {
        "artifacts": {
            PAYLOAD: {
                "path": str(OUT_PATH),
                "sha256": sha256_file(OUT_PATH),
                "count": len(rows),
                "reviewed_count": len(rows) - len(automatic),
                "automatic_count": len(automatic),
                "generated_at": _stamp_utc(generated_at),
                "reviewed_at": document["reviewed_at"],
            }
        }
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    print(
        f"Wrote {len(rows)} ATC update(s) to {OUT_PATH}: {len(rows) - len(automatic)} reviewed "
        f"{document['reviewed_at']}, {len(automatic)} published automatically since."
    )
    for row in automatic:
        print(f"  auto: {row['atc_id']} at NOBO {row['start_mile_marker']} ({row['category']})")
    if refusals:
        # These are ATC's newest, refused for something a person can resolve:
        # several mile references, a category this build does not know, wording
        # that may be an all-clear. They are exactly the proposer's input in
        # #463 - A job that proposes parsed ATC updates as a pull request,
        # never publishes them - and are named rather than counted so a
        # reviewer can go straight to them.
        print(f"  {len(refusals)} posted since the review but NOT auto-published:")
        for refusal in refusals:
            print(f"    - {refusal}")
    return manifest


if __name__ == "__main__":
    main()
