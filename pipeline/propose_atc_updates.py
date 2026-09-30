"""Draft `reference/atc_updates_proposed.json` from what ATC posted that
#963's gate could not publish on its own (#463).

    python propose_atc_updates.py

WHAT THIS IS FOR. #963 closed the gap where a hiker only heard about a new
ATC notice if a person happened to look: every update whose mile reference is
unambiguous, in a category this build knows, and edited since the last
review now publishes on its own, hourly, with `obstructs_trail` forced
false. What is left after that gate runs is exactly the set #463 was written
about - Iron Mtn Gap's five accumulated ranges, a category ATC has not used
before, wording that might be an all-clear - and until now the only place
that set was written down was a workflow log nobody reads until #478 or #945
happens again.

THIS SCRIPT NEVER PUBLISHES ANYTHING. It writes a second file,
`reference/atc_updates_proposed.json`, that nothing in the publish pipeline
reads - not `export_atc_updates.py`, not `publish.py`, not a client. A
scheduled workflow runs this, and if the candidate list changed, opens a
pull request carrying the diff. A human reads each candidate beside ATC's
own page and, if it is right, types the row into `reference/atc_updates.json`
by hand - the same reviewed-file path #460 already proved. This file is the
proposer's whole output: a draft for a person to check, never a row a person
skipped checking.

WHY A SEPARATE FILE RATHER THAN A DRAFT ROW IN THE REVIEWED ONE. The reviewed
file is what `export_atc_updates.py` bakes hourly, and
`test_lib_atc_updates.py` holds it to `file_problems() == []` - every row
complete, every mile inside the trail's own extent. A candidate here is
missing exactly the thing a person has to supply: which one of several mile
references is current, or whether the wording means the trail reopened. A
row that cannot answer that has no honest value to put in
`start_mile_marker`, and forcing one - null, zero, the first parsed
reference - would either fail that test file's own assertion against the
committed reviewed file or, worse, pass it with a wrong number ATC never
confirmed. A second file makes "not yet checked" a location rather than a
convention.

WHAT MAKES THIS THE SAME CANDIDATE SET #963'S JOB LOG ALREADY PRINTS.
`lib.atc_updates.auto_publish_refusal` is the one gate; this reads the same
reasons `export_atc_updates.py`'s `automatic_rows` does, filtered by the same
rule that function's own comment states inline - a notice already reviewed or
not edited since the review is the steady state and is refused on every run,
not a finding. That filter is duplicated here (`_actionable`) rather than
imported from a shared home in `lib/`, and deliberately: every publishing
workflow's `pipeline_scopes.py` scope treats all of `pipeline/lib/` as shared
root, so editing that directory stales `build-basemap.yml`, `build-dem.yml`
and `publish-vector-data.yml` too, on a change none of them can possibly be
affected by. A few duplicated lines here cost far less than four unnecessary
`ua` rebuilds every time this file changes. What is left after the gate runs
is small by construction: `sources.json`'s own steward note on this source
and features/ATC_TRAIL_UPDATES.md section 6 both measured "roughly nine
updates edited weekly" before #963 shipped and turned out to undercount by an
order of magnitude for the full unreviewed backlog; the residue after #963's
gate runs is close to that original estimate, because #963 is precisely what
now clears the mechanical majority.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from lib.atc_updates import auto_publish_refusal
from lib.hashing import sha256_file
from lib.manifest_paths import to_manifest_path

ROOT = Path(__file__).resolve().parent
REVIEWED_PATH = ROOT / "reference" / "atc_updates.json"
OUT_PATH = ROOT / "reference" / "atc_updates_proposed.json"
CACHE_PATH = ROOT / "data" / "raw" / "atc_updates.json"


def _actionable(refusal: str) -> bool:
    """Same rule `export_atc_updates.py`'s `automatic_rows` filters its job-log
    lines by - see that function's comment for why the other two reasons
    (already reviewed, older than the review) are the steady state rather
    than a finding. Kept in sync by `test_propose_atc_updates.py` and
    `test_lib_atc_updates.py` both asserting the same refusal strings; not
    imported, for the reason above the imports."""
    return not (refusal.startswith("already reviewed") or refusal.startswith("last edited"))


def _stamp_utc(value: datetime) -> str:
    """Same `...Z` convention as export_atc_updates.py, for the same reason:
    a naive stamp is read as local time by `new Date()`."""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _updated_at_stamp(iso: str) -> str:
    """ATC's `dateModified`, converted the same way `lib.atc_updates.auto_row`
    converts it for the reviewed artifact - duplicated for the same reason
    `_actionable` is: this file must not edit anything under `pipeline/lib/`."""
    try:
        stamped = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if stamped.tzinfo is None:
        stamped = stamped.replace(tzinfo=timezone.utc)
    return stamped.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mile_reference(mile) -> dict:
    return {"direction": mile.direction, "start": mile.start, "end": mile.end, "raw": mile.raw}


def build_candidates(document: dict, parsed: list) -> list[dict]:
    """One draft per actionable refusal, carrying everything the parse knows
    and nothing it had to guess.

    Ordered by slug, same as `automatic_rows`, so a rerun with nothing new
    produces byte-identical output and the workflow's diff check is not
    fooled by reordering.
    """
    reviewed_ids = {row["atc_id"] for row in document["updates"]}
    reviewed_at = document["reviewed_at"]

    candidates = []
    for update in sorted(parsed, key=lambda u: u.slug):
        refusal = auto_publish_refusal(update, reviewed_ids, reviewed_at)
        if refusal is None or not _actionable(refusal):
            continue
        candidates.append(
            {
                "atc_id": update.slug,
                "title": update.title.strip() if update.title else update.title,
                "category": update.category,
                "states": list(update.states),
                "mile_references": [_mile_reference(m) for m in update.miles],
                "updated_at": _updated_at_stamp(update.date_modified) if update.date_modified else None,
                "source_url": update.source_url,
                "reason_not_auto_published": refusal,
            }
        )
    return candidates


def build_document(document: dict, generated_at: datetime, candidates: list[dict]) -> dict:
    return {
        "generated_at": _stamp_utc(generated_at),
        # The reviewed file's own baseline, carried along so a reader of this
        # file alone can tell how old the review is that these candidates are
        # measured against - the same reason export_atc_updates.py's artifact
        # carries it.
        "reviewed_at": document["reviewed_at"],
        "candidates": candidates,
    }


def cached_updates(path: Path | None = None) -> list:
    """`fetch_atc_updates.py`'s cache, rehydrated - the same reader
    `export_atc_updates.py` uses, duplicated rather than imported because
    that copy is private to a script this one must not depend on (a bake
    failure must never cost a proposal, or the other way round)."""
    from lib.atc_scrape import MileReference, ParsedUpdate

    path = path or CACHE_PATH
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    entries = raw.get("updates")
    if not isinstance(entries, dict):
        return []

    parsed = []
    for slug, entry in entries.items():
        if not isinstance(entry, dict) or not entry.get("listed", True):
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


def main() -> dict | None:
    document = json.loads(REVIEWED_PATH.read_text())

    if not document.get("reviewed_at"):
        # Same stance as export_atc_updates.py: nobody has reviewed the file
        # yet, so there is no baseline to measure "posted since" against.
        # Nothing written, exit 0 - a true statement about where the feature
        # has got to, not a failure.
        print(f"{REVIEWED_PATH.name} has no reviewed_at yet - nothing to propose against.")
        return None

    generated_at = datetime.now(timezone.utc)
    candidates = build_candidates(document, cached_updates())
    out_document = build_document(document, generated_at, candidates)
    OUT_PATH.write_text(json.dumps(out_document, indent=2) + "\n")

    manifest = {
        "generated_at": _stamp_utc(generated_at),
        "path": to_manifest_path(OUT_PATH),
        "sha256": sha256_file(OUT_PATH),
        "candidate_count": len(candidates),
    }

    print(f"Wrote {len(candidates)} candidate(s) to {OUT_PATH}.")
    for candidate in candidates:
        print(f"  {candidate['atc_id']}: {candidate['reason_not_auto_published']}")
    return manifest


if __name__ == "__main__":
    main()
