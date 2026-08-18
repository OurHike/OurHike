"""What a fetcher leaves behind to prove it finished, and how packaging reads it.

Every fetcher in this pipeline talks to a third party, and until #542 the
design required all of them to succeed inside one process for any of them to
count. Run 31592776758 died on a USGS 504 at step 13 and discarded twelve
completed steps - ArcGIS sources, opentrail POIs, photos, trail lines, POIs,
spurs - none of which depended on elevation.

**The fetchers were never the problem.** All six already write a durable
output, atomically: fetch_all.py gates every registered source before writing
data/raw/manifest.json, fetch_opentrail.py keeps a 50% shrink guard in front
of its etag, fetch_topo_quads.py persists each quad as it lands,
fetch_elevation.py has write-gate tolerances on tile_index.json, and both
photo fetchers write through a temp file and os.replace. What was missing is
one layer up: nothing reads ACROSS them, so packaging cannot tell an output
that is a week old from one that was never fetched at all. #542 names that
distinction as the thing that has to be visible rather than inferred.

WHAT A RECEIPT IS, AND WHAT IT DELIBERATELY IS NOT
--------------------------------------------------
A receipt says "this fetcher ran to completion at this time, and stands
behind these files, which hashed to this". That is all.

It does NOT record the upstream markers - opentrail's etag, ArcGIS's
dataLastEditDate, USGS's Last-Modified. Those already live in each fetcher's
own state file, where the fetcher's skip decision reads them, and copying
them here would be a second home for the contract: exactly the failure
verify_release.py's docstring describes about parsing config.ts, and exactly
what this repository keeps finding. A receipt is about THIS RUN's completion;
freshness of the SOURCE stays with check_freshness.py and build_state.json.

ONE FILE PER FETCHER, which is load-bearing rather than tidy. A single
shared receipts.json would have to be read-modify-written by every fetcher,
so two fetchers running independently - the entire point of #542 - would race
on it, and a fetcher that died mid-write would take the other five's records
with it. Separate files make the independence real: a fetcher can only ever
damage its own receipt.

PATHS ARE RECORDED RELATIVE to the pipeline root, unlike the export
manifests, which record absolute paths (export_trails.py:387). That is not a
style preference. publish-vector-data.yml keeps building and publishing in
one job specifically because those absolute paths "only agree on one
filesystem", and calls splitting them "a trap rather than a design". Receipts
are meant to survive between runs on different runners, so they cannot carry
the same trap.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from lib.hashing import sha256_file

#: Where receipts live, under the gitignored data/ tree. Beside data/raw's
#: own outputs rather than in data/processed, because a receipt describes a
#: FETCH - what came off the network - not anything an export derived.
RECEIPTS_DIR = Path("data") / "raw" / "receipts"

#: Fetchers whose output every release needs, whatever else was requested.
#:
#: Both, and only these two, because export_poi.py cannot run without either:
#: fetch_all.py covers the ArcGIS layers, opentrail.org is a different API
#: with its own script, and the export reads its output directly
#: (export_poi.py:108). publish-vector-data.yml says the same thing in prose
#: above its two fetch steps - "both fetches are required before any export" -
#: and runs them unconditionally. This is a property of the code rather than a
#: choice a particular run makes, which is why it is a constant here and not a
#: flag the workflow passes.
REQUIRED_FETCHERS = ("fetch_all", "fetch_opentrail")

#: Fetchers allowed to leave no receipt at all without failing a release.
#:
#: One member, and its reason is already written into the workflow:
#: fetch_poi_images.py carries `continue-on-error: true` because Commons
#: "is a third-party API this project has no relationship with - so a Commons
#: outage must not be able to block a trail-data release". A gate that failed
#: on its absence would contradict the step that produces it. Reported anyway,
#: with its age, because silently shipping without photos is how the missing
#: ATC photos went unnoticed when that source was added.
#:
#: fetch_atc_photos.py is deliberately NOT here. Its step has no
#: continue-on-error, and the workflow explains why: it reads the same ATC
#: data the export is built from, so if it is unreachable "the release has
#: bigger problems than missing photos".
ADVISORY_FETCHERS = ("fetch_poi_images",)


def _root(root: Path | None) -> Path:
    """The pipeline directory. Defaults to this file's parent's parent so
    callers in pipeline/ need not pass anything; tests pass a tmp_path."""
    return Path(__file__).resolve().parent.parent if root is None else Path(root)


def receipts_dir(root: Path | None = None) -> Path:
    return _root(root) / RECEIPTS_DIR


def receipt_path(fetcher: str, root: Path | None = None) -> Path:
    return receipts_dir(root) / f"{fetcher}.json"


def _record_path(path: Path, root: Path) -> str:
    """How one output's location is written down.

    Relative to the pipeline root wherever possible, which is every real
    fetcher on every real run - all of them write under data/. The absolute
    fallback is for an output pointed somewhere else entirely, which in
    practice means a test that redirected a fetcher's OUT_PATH to a tmp
    directory.

    Falling back rather than raising is deliberate: refusing would turn
    "a caller put its output somewhere unusual" into a fetch that reports
    failure, which is a much worse answer than a path that happens not to be
    portable. The receipt still verifies correctly either way; what it loses
    is survival across runners, and an output outside the pipeline tree was
    never going to be restored from a cache anyway."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def describe(path: Path, root: Path | None = None) -> dict:
    """One output's entry: where it is, how big it is, and what it hashes to.

    Raises if the file is not there - a fetcher calling this is asserting it
    just wrote the thing, so a missing file at that moment is a bug in the
    fetcher and must not be recorded as a successful fetch."""
    path = Path(path)
    return {
        "path": _record_path(path, _root(root)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def record(
    fetcher: str,
    outputs,
    *,
    root: Path | None = None,
    now: datetime | None = None,
) -> dict:
    """Write `fetcher`'s receipt and return it.

    Called at the very end of a fetcher's main(), AFTER its own completeness
    gate - a receipt means "this finished", so writing one before the gate
    that can still sys.exit(1) would record a run that failed as a run that
    worked.

    Written through a temp file and os.replace, matching what the outputs it
    describes already do. A receipt torn in half by a killed process would be
    read as corrupt by the gate below, which fails the release; that is the
    safe direction, but there is no reason to leave it possible."""
    when = datetime.now(timezone.utc) if now is None else now
    receipt = {
        "fetcher": fetcher,
        "completed_at": when.isoformat(),
        "outputs": [describe(Path(p), root=root) for p in outputs],
    }

    path = receipt_path(fetcher, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / (path.name + ".tmp")
    tmp_path.write_text(json.dumps(receipt, indent=2, sort_keys=True))
    os.replace(tmp_path, path)
    return receipt


def load(fetcher: str, root: Path | None = None) -> dict | None:
    """A fetcher's receipt, or None if it has never left one.

    A present-but-unparseable receipt raises rather than returning None, the
    same split read_manifest() makes in check_output_quality.py: "never
    fetched" and "fetched and the record is corrupt" are different problems
    and must not collapse into one message."""
    path = receipt_path(fetcher, root)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def verify(receipt: dict, root: Path | None = None) -> list[str]:
    """Problems with what a receipt claims, checked against the bytes on disk
    right now - not against what the fetcher believed when it exited.

    This is check_output_quality.py's artifact_problems() reasoning applied
    one layer upstream: a same-process check can only ever confirm its own
    belief about its own output. Between the fetch and the package the file
    can be truncated by a full disk, half-restored from a cache, or edited;
    re-hashing is the only thing that notices."""
    fetcher = receipt.get("fetcher", "?")
    outputs = receipt.get("outputs")
    if not outputs:
        return [f"{fetcher}: receipt claims no outputs"]

    problems = []
    for entry in outputs:
        relative = entry.get("path")
        if not relative:
            problems.append(f"{fetcher}: receipt entry has no path")
            continue

        # `/` leaves an absolute right-hand side untouched, so this resolves
        # both forms _record_path() can write without asking which it got.
        path = _root(root) / relative
        if not path.exists():
            problems.append(f"{fetcher}: {relative} is in the receipt and not on disk")
            continue

        recorded_hash = entry.get("sha256")
        actual_hash = sha256_file(path)
        if actual_hash != recorded_hash:
            problems.append(
                f"{fetcher}: {relative} changed since it was fetched - "
                f"receipt says {recorded_hash!r}, file on disk hashes to {actual_hash!r}"
            )

    return problems


def age_days(receipt: dict, now: datetime | None = None) -> float | None:
    """How long ago this fetcher finished, in days, or None if the receipt
    carries no readable timestamp.

    Never a problem on its own. #542 is explicit that "a release built while
    poi_images.json is a week old is a legitimate release" - staleness is
    something packaging has to SAY, so a reader can judge it, rather than
    something it decides on their behalf."""
    stamp = receipt.get("completed_at")
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    reference = datetime.now(timezone.utc) if now is None else now
    return (reference - when).total_seconds() / 86400.0


def expected_fetchers(fetched=()) -> list[str]:
    """Which fetchers this run has to be able to show a receipt for.

    The always-required pair, plus whatever the caller says it ran this time.
    Deduplicated and ordered so the report reads the same way twice.

    Split like this because only the caller knows the second half: photos and
    elevation are workflow_dispatch inputs, so "did this run fetch elevation"
    is a fact about the run, while "a release needs the ArcGIS layers" is a
    fact about the code. Keeping the run-specific half as an argument is the
    same shape check_output_quality.py's --optional already uses, and for the
    same reason - a gate that assumed the full set would contradict the
    partial publishes publish.py supports."""
    ordered = list(REQUIRED_FETCHERS)
    for name in fetched:
        if name not in ordered:
            ordered.append(name)
    return ordered
