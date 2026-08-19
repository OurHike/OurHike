"""Own every published POI id across upstream refreshes (#671).

features/POI_IDENTITY.md is the design; this is build-order steps 1 and 2
(#671, #672): the ledger, tier 1 (the key survived), the teleport guard,
`--check`, tier 2 (evidence matching), and the overrides file. The
problem it closes is #666's: `unify_poi` mints every published id as
`{source}:{source_feature_id}`, which holds only while upstream's keys hold
still - and one ATC republish re-mints every GlobalID, orphaning every
photo, note and capacity line anchored to the old ids, silently.

THE LEDGER. `reference/poi_identity.json`, checked in for the same reason
`reference/shelter_capacity.json` is: each identity decision is a
reviewable line in a diff, and a release build never depends on the network
to know who anyone is. One row per POI ever published, keyed by the OurHike
id, serialized ONE ROW PER LINE so a refresh's identity outcome reads as a
per-place diff (and so the file stays under test_no_committed_data.py's
reference-review ceiling). Three rules, and they are the contract:

  - never re-mint an id for a place that persists, whatever happened to its
    upstream key, name, position or source;
  - never reuse an id, however long its row has been retired;
  - never delete a row - retirement is an event in a place's history.

The id string is a birthmark, not a pointer: minted from where the place
was FIRST seen, kept verbatim forever. Provenance is the
`source`/`source_feature_id` properties. Nothing may parse an id to learn
its source.

THREE TIERS, BY EVIDENCE. Tier 1: a record whose
`(source, source_feature_id)` matches a live row carries that row's id,
and the row's name/position/fingerprint update silently - those facts are
upstream's to change. Tier 2 (#672): over the bipartite set of
disappeared rows x unmatched new features, blocked by poi_type, score
distance, normalised name, the inventory fingerprint and along-trail
position - and accept only on three conditions (threshold, margin over
the runner-up on both sides, a hard distance ceiling min()'d against
everything) plus mutual-best. Tier 3: everything else retires and
creates - the default precisely because it is the RECOVERABLE mistake: a
later `same` override re-unites a tombstone with its successor, where a
confident wrong merge cannot be unmade. A wholesale upstream re-mint
that tier 2 cannot mostly carry still refuses to write (the retire-share
guard below), staying a loud, blocked event.

OVERRIDES are `reference/poi_identity_overrides.json` - hand-written,
never touched by this script: `same` rows carry an id onto a named key
before any scoring (the one door back in for a tombstone), `not_same`
rows forbid a pair. Each row carries a reason.

HELD FOR REVIEW, not carried, when the evidence is suspicious:

  - a surviving key whose feature moved over TELEPORT_MILES - key reuse is
    rare and conceivable, and a shelter teleporting is evidence of it;
  - a surviving key whose feature changed poi_type - an id never crosses
    type;
  - a new feature whose derived id already belongs to a retired row -
    minting it would reuse an id, which nothing may do (`same` override =
    the door back in);
  - a `same` override naming a key this snapshot does not leave unmatched -
    a stale override is a decision quietly stopped being applied.

A held item makes the run fail (exit 2) writing nothing, so nothing
publishes until a human looks.

--check IS THE CI GATE. The checked-in ledger must be exactly what this
reconciliation produces from the raw snapshot plus the checked-in ledger
itself - `build_shelter_capacity.py --check`'s pattern. A refresh that
changes identity therefore cannot publish until the ledger diff has been
regenerated, committed and reviewed. Run by publish-vector-data.yml after
the fetches, before the exports.

    python reconcile_poi_identity.py            update the ledger, print the summary
    python reconcile_poi_identity.py --check    verify the checked-in ledger, write nothing
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lib.spurs import distance_m

ROOT = Path(__file__).parent
LEDGER_PATH = ROOT / "reference" / "poi_identity.json"
# Machine-owned ledger, human-owned overrides (#672): `same` rows carry an
# id onto a named key before scoring, `not_same` rows forbid a pair. This
# script READS the file and never writes it - the same split sources.json
# keeps between discovered and hand-added entries.
OVERRIDES_PATH = ROOT / "reference" / "poi_identity_overrides.json"

METERS_PER_MILE = 1609.344

# The teleport guard's line (features/POI_IDENTITY.md tier 1): "a surviving
# key whose feature moved implausibly far (over a mile) is held for review
# rather than carried". The ATC refresh that actually ships moves things "a
# few feet"; a mile is ~three orders of magnitude past that, far enough
# that a legitimate correction cannot plausibly reach it.
TELEPORT_MILES = 1.0

# Refuse to write a run that retires this share of the live ledger. Tier 2
# carries what the evidence supports; what remains past this share is a
# wholesale re-mint the evidence could NOT recognise, and the only safe
# output for that is no output - a human and the overrides file are the
# path through. The count floor keeps the guard out of the way of small
# synthetic ledgers and genuinely small prunings.
# @unvalidated - both numbers are reasoned (a real ATC year removes a
# handful of features, not a fifth of the trail), not measured; #675 -
# Measure the first real ATC refresh is where the measurement lands.
MAX_RETIRE_SHARE = 0.2
MIN_RETIRES_FOR_GUARD = 25

# --- Tier 2 (#672): the evidence, and the three-condition acceptance -------
#
# Every signal is one this repository already measured the worth of, per the
# design: lib/spurs.distance_m, lib/poi_sites' name normalisation, the
# marker-calibrated trail axis, and ATC's own inventory fingerprint
# (Year_Built/Stories/Exterior_M are non-null on all 280 shelters;
# Year_Built on 308 of 316 privies). The CONSTANTS are calibration, not
# design - the structure (threshold + margin + ceiling + mutual-best) is
# the decision, and #675 - Measure the first real ATC refresh is where
# these numbers get settled and recorded with what they changed from.
# @unvalidated - all of them, reasoned as follows and measured never.

# The hard ceiling, applied as min() against everything else - the 903 km
# lesson: a matcher's gates get widened by future hands, and the ceiling is
# what survives them. Drawn at the same line the tier-1 teleport guard
# draws, for the same reason: the refresh ATC actually ships moves things
# "a few feet", and a mile is ~three orders of magnitude past that.
MATCH_CEILING_M = TELEPORT_MILES * METERS_PER_MILE

# Score contributions. A normalised-name match is strong evidence (ATC's
# own misspellings normalise together); a bare base-name match ("laurel
# ridge" from "Laurel Ridge Campsite 2") is weak alone - the Laurel Ridge
# lesson. An intact multi-field fingerprint is a passport ("built 1938,
# one storey, log"); a CONFLICTING one is stronger negative evidence than
# any positive signal here is positive, because upstream does not rebuild
# a shelter by accident.
SCORE_NAME_EXACT = 2.0
SCORE_NAME_BASE = 1.0
SCORE_FINGERPRINT_FULL = 2.0  # >= 2 shared fields, all equal
SCORE_FINGERPRINT_THIN = 1.0  # 1 shared field, equal
SCORE_FINGERPRINT_CONFLICT = -3.0
SCORE_NEAR = 1.0
NEAR_DISTANCE_M = 50.0
SCORE_MILE = 0.5
NEAR_MILE = 0.25

# Acceptance: clear the threshold, clear it by a margin over the runner-up
# ON BOTH SIDES, and be mutual best. 2.5 means no single signal suffices:
# a name alone (2.0) or proximity alone (1.5 with the mile) retires-and-
# creates instead, the recoverable default.
ACCEPT_THRESHOLD = 2.5
ACCEPT_MARGIN = 1.0

# The inventory fields that make a facility close to uniquely identifiable
# independent of name and position - carried on ledger rows so a future
# snapshot's features can be matched against what the place USED to say
# about itself.
FINGERPRINT_FIELDS = ("Year_Built", "Stories", "Exterior_M")

_README = [
    "The POI identity ledger (features/POI_IDENTITY.md, #671): one row per",
    "POI ever published, keyed by the OurHike id. GENERATED by",
    "reconcile_poi_identity.py - re-run that script rather than editing rows",
    "here, and review the diff it produces; CI holds this file to exactly",
    "what reconciliation reproduces (--check).",
    "",
    "Three rules: never re-mint an id for a place that persists, never reuse",
    "an id, never delete a row. The id string is a birthmark - provenance is",
    "the source/source_feature_id properties, and nothing may parse an id to",
    "learn its source.",
]


@dataclass
class Outcome:
    """One reconciliation's result: the next ledger, and what happened.

    `matched` is tier 2's list (#672), one human sentence per carry naming
    its evidence - per the design's rule that a bare reference tells the
    reader nothing."""

    pois: dict
    carried: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    minted: list[str] = field(default_factory=list)
    retired: list[str] = field(default_factory=list)
    held: list[str] = field(default_factory=list)


def live_rows(pois: dict) -> dict:
    return {poi_id: row for poi_id, row in pois.items() if "retired" not in row}


def _refresh_from(row: dict, record: dict) -> None:
    """The upstream-owned fields, taken silently: what a place is called,
    where it is, and what its inventory says about it."""
    row["name"] = record.get("name")
    row["lat"] = record["lat"]
    row["lon"] = record["lon"]
    fingerprint = record.get("fingerprint")
    if fingerprint:
        row["fingerprint"] = fingerprint
    else:
        row.pop("fingerprint", None)


def _fingerprint_verdict(old: dict | None, new: dict | None) -> tuple[str, float]:
    """('intact'|'thin'|'conflict'|'absent', score contribution)."""
    shared = sorted(set(old or {}) & set(new or {}))
    if not shared:
        return "absent", 0.0
    if any(old[key] != new[key] for key in shared):
        return "conflict", SCORE_FINGERPRINT_CONFLICT
    if len(shared) >= 2:
        return "intact", SCORE_FINGERPRINT_FULL
    return "thin", SCORE_FINGERPRINT_THIN


def _score_pair(row: dict, record: dict, mile_delta: float | None) -> tuple[float, str] | None:
    """One (disappeared row, unmatched feature) pair's score and its
    evidence sentence, or None when the pair is outside the hard ceiling -
    which is min()'d against everything: no other signal can buy a pair
    back in past it."""
    from lib.poi_sites import base_name, normalise_name

    d = distance_m(row["lat"], row["lon"], record["lat"], record["lon"])
    if d > MATCH_CEILING_M:
        return None

    score = 0.0
    evidence = [f"{d:.0f} m"]
    if normalise_name(row.get("name")) and normalise_name(row.get("name")) == normalise_name(record.get("name")):
        score += SCORE_NAME_EXACT
        evidence.append("name intact")
    elif base_name(row.get("name")) and base_name(row.get("name")) == base_name(record.get("name")):
        score += SCORE_NAME_BASE
        evidence.append("base name intact")

    verdict, contribution = _fingerprint_verdict(row.get("fingerprint"), record.get("fingerprint"))
    score += contribution
    if verdict != "absent":
        evidence.append(f"fingerprint {verdict}")

    if d <= NEAR_DISTANCE_M:
        score += SCORE_NEAR
    if mile_delta is not None and abs(mile_delta) <= NEAR_MILE:
        score += SCORE_MILE
        evidence.append(f"Δmile {abs(mile_delta):.2f}")

    return score, ", ".join(evidence)


def match_by_evidence(
    disappeared: dict[str, dict],
    unmatched: list[dict],
    forbidden: set[tuple[str, tuple[str, str]]],
    mile_of=None,
) -> list[tuple[str, int, str]]:
    """Tier 2 (#672): (poi_id, record index, evidence) for every accepted
    match over the bipartite set, blocked by poi_type.

    Acceptance is three conditions, not a bare score, each bought by a
    failure already in this repository: clear ACCEPT_THRESHOLD, clear the
    runner-up by ACCEPT_MARGIN on BOTH sides (the Laurel Ridge tie-break
    lesson - two candidates that reduce alike go to retirement, not to a
    guess), and sit inside MATCH_CEILING_M (the 903 km lesson). Matches
    must be mutual best. Anything short of all three retires-and-creates,
    the recoverable default.

    `mile_of`, when given, is a batch callable [(lat, lon), ...] ->
    [mile | None, ...] - the along-trail position signal, robust to exactly
    the lateral corrections that move lat/lon. Optional because it needs
    the calibrated axis, which synthetic tests rightly do not have.
    """
    miles: dict[tuple[float, float], float | None] = {}
    if mile_of is not None and disappeared and unmatched:
        points = [(row["lat"], row["lon"]) for row in disappeared.values()]
        points += [(record["lat"], record["lon"]) for record in unmatched]
        for point, mile in zip(points, mile_of(points)):
            miles[point] = mile

    def delta(row: dict, record: dict) -> float | None:
        old = miles.get((row["lat"], row["lon"]))
        new = miles.get((record["lat"], record["lon"]))
        if old is None or new is None:
            return None
        return new - old

    by_old: dict[str, list[tuple[float, int, str]]] = {}
    by_new: dict[int, list[tuple[float, str]]] = {}
    for poi_id, row in disappeared.items():
        for index, record in enumerate(unmatched):
            if record["poi_type"] != row["poi_type"]:
                continue
            if (poi_id, (record["source"], record["source_feature_id"])) in forbidden:
                continue
            scored = _score_pair(row, record, delta(row, record))
            if scored is None:
                continue
            score, evidence = scored
            by_old.setdefault(poi_id, []).append((score, index, evidence))
            by_new.setdefault(index, []).append((score, poi_id))

    def clears(ranked: list, top_score: float) -> bool:
        if top_score < ACCEPT_THRESHOLD:
            return False
        return len(ranked) < 2 or top_score - ranked[1][0] >= ACCEPT_MARGIN

    accepted = []
    for poi_id, candidates in by_old.items():
        candidates.sort(key=lambda entry: -entry[0])
        score, index, evidence = candidates[0]
        if not clears(candidates, score):
            continue
        rivals = sorted(by_new[index], key=lambda entry: -entry[0])
        if rivals[0][1] != poi_id or not clears(rivals, rivals[0][0]):
            continue
        accepted.append((poi_id, index, evidence))
    return accepted


def reconcile(
    pois: dict,
    records: list[dict],
    release: str,
    overrides: dict | None = None,
    mile_of=None,
) -> Outcome:
    """Tiers 1 and 2 over `records` (this snapshot's publishable POIs)
    against `pois` (the prior ledger's rows). Pure - no I/O - so the tests
    can hold every branch without a corridor on disk.

    `overrides` is the hand-owned file's content (#672): `same` rows carry
    an id onto a named key before any scoring (and may resurrect a
    tombstone - the one door back in), `not_same` rows forbid a pair the
    matcher would otherwise consider. Machine-owned ledger, human-owned
    overrides; nothing here ever writes the latter.
    """
    next_pois = {poi_id: dict(row) for poi_id, row in pois.items()}
    by_key = {(row["source"], row["source_feature_id"]): poi_id for poi_id, row in live_rows(pois).items()}

    outcome = Outcome(pois=next_pois)
    seen_ids: set[str] = set()
    unmatched: list[dict] = []

    # --- Tier 1: the key survived -----------------------------------------
    for record in records:
        key = (record["source"], record["source_feature_id"])
        poi_id = by_key.get(key)

        if poi_id is None:
            unmatched.append(record)
            continue
        if poi_id in seen_ids:
            outcome.held.append(
                f"{poi_id}: two records in ONE snapshot carry the same upstream key - a source is "
                "emitting duplicates, and neither can own the id until a human says which is the place"
            )
            continue
        row = next_pois[poi_id]
        moved_m = distance_m(row["lat"], row["lon"], record["lat"], record["lon"])
        if moved_m > TELEPORT_MILES * METERS_PER_MILE:
            outcome.held.append(
                f"{poi_id}: key survived but the feature moved {moved_m / METERS_PER_MILE:.1f} mi "
                f"({row['name']!r} -> {record.get('name')!r}) - key reuse is the suspicion, review before carrying"
            )
            continue
        if record["poi_type"] != row["poi_type"]:
            outcome.held.append(
                f"{poi_id}: key survived but poi_type changed {row['poi_type']} -> {record['poi_type']} - "
                "an id never crosses type; review before carrying"
            )
            continue
        # Carried, silently: name, position and inventory are upstream's.
        _refresh_from(row, record)
        seen_ids.add(poi_id)
        outcome.carried.append(poi_id)

    disappeared = {
        poi_id: next_pois[poi_id]
        for poi_id in live_rows(pois)
        if poi_id not in seen_ids and not any(h.startswith(f"{poi_id}:") for h in outcome.held)
    }

    def carry_onto(poi_id: str, record: dict, by: str, evidence: str, reason: str | None = None) -> None:
        row = next_pois[poi_id]
        event = {
            "release": release,
            "event": "matched",
            "by": by,
            "source_feature_id_was": row["source_feature_id"],
            "name_was": row.get("name"),
        }
        if reason:
            event["reason"] = reason
        if "retired" in row:
            # The override door back in: a tombstone re-united with its
            # successor, which is the whole point of retirement being the
            # recoverable mistake.
            event["was_retired"] = row.pop("retired")
        row["history"] = [*row.get("history", []), event]
        row["source"] = record["source"]
        row["source_feature_id"] = record["source_feature_id"]
        row["poi_type"] = record["poi_type"]
        _refresh_from(row, record)
        seen_ids.add(poi_id)
        outcome.matched.append(f"{poi_id}: {evidence}")

    # --- Overrides: the human speaks before the matcher does --------------
    overrides = overrides or {}
    forbidden = {(entry["id"], (entry["source"], entry["source_feature_id"])) for entry in overrides.get("not_same", [])}
    for entry in overrides.get("same", []):
        poi_id = entry["id"]
        match = next(
            (
                (index, record)
                for index, record in enumerate(unmatched)
                if (record["source"], record["source_feature_id"]) == (entry["source"], entry["source_feature_id"])
            ),
            None,
        )
        if poi_id not in next_pois or poi_id in seen_ids or match is None:
            # An override naming nothing present is stale the moment upstream
            # moves again - said out loud rather than silently skipped.
            outcome.held.append(
                f"{poi_id}: a `same` override names key ({entry['source']}, {entry['source_feature_id']}), "
                "which this snapshot does not leave unmatched - the override is stale; remove or fix it"
            )
            continue
        index, record = match
        carry_onto(
            poi_id,
            record,
            by="override",
            evidence=f"override ({entry.get('reason', 'no reason given')})",
            reason=entry.get("reason"),
        )
        unmatched.pop(index)
        disappeared.pop(poi_id, None)

    # --- Tier 2: the key did not survive; the evidence might --------------
    matched_indices: set[int] = set()
    for poi_id, index, evidence in match_by_evidence(disappeared, unmatched, forbidden, mile_of):
        record = unmatched[index]
        carry_onto(poi_id, record, by="evidence", evidence=f"{row_arrow(next_pois[poi_id], record)}, {evidence}")
        matched_indices.add(index)
        disappeared.pop(poi_id, None)

    # --- Tier 3: everything else retires and creates ----------------------
    for index, record in enumerate(unmatched):
        if index in matched_indices:
            continue
        minted = record["id"]
        if minted in seen_ids:
            outcome.held.append(
                f"{minted}: two records in ONE snapshot derive the same id - a source is emitting "
                "duplicate keys, and neither can own the id until a human says which is the place"
            )
            continue
        if minted in next_pois:
            # A live row would have matched by key above, so this is a
            # retired id resurfacing - and reusing it is the one thing the
            # contract forbids outright.
            outcome.held.append(
                f"{minted}: upstream re-presents the key of a RETIRED row ({next_pois[minted].get('name')!r}) - "
                "ids are never reused; if this is the same place returning, a `same` override is the door back in"
            )
            continue
        next_pois[minted] = {
            "poi_type": record["poi_type"],
            "source": record["source"],
            "source_feature_id": record["source_feature_id"],
            "name": record.get("name"),
            "lat": record["lat"],
            "lon": record["lon"],
            "first_seen": release,
            "history": [],
        }
        if record.get("fingerprint"):
            next_pois[minted]["fingerprint"] = record["fingerprint"]
        seen_ids.add(minted)
        outcome.minted.append(minted)

    for poi_id in disappeared:
        gone = next_pois[poi_id]
        gone["retired"] = release
        gone["history"] = [*gone.get("history", []), {"release": release, "event": "retired"}]
        outcome.retired.append(poi_id)

    return outcome


def row_arrow(row: dict, record: dict) -> str:
    """'Winturri Shelter' -> 'Wintturi Shelter', or just the name when it
    did not change - the design's own example sentence shape."""
    was, now = row.get("name"), record.get("name")
    return f"{was!r}" if was == now else f"{was!r} -> {now!r}"


def mass_retirement_refusal(outcome: Outcome, prior: dict) -> str | None:
    """The sentence that refuses a wholesale re-mint, or None when the run
    is a refresh-shaped one. See MAX_RETIRE_SHARE."""
    live = len(live_rows(prior))
    share = len(outcome.retired) / max(1, live)
    if len(outcome.retired) < MIN_RETIRES_FOR_GUARD or share <= MAX_RETIRE_SHARE:
        return None
    return (
        f"REFUSED: this run would retire {len(outcome.retired)} of {live} live rows "
        f"({share:.0%}) - the shape of a wholesale upstream re-mint, not of a refresh. "
        "Nothing was written; #672's evidence matching is the recovery path, not a mass retirement."
    )


def render(pois: dict) -> str:
    """The ledger's serialization: one row per line, sorted by id, so a
    refresh's identity outcome reads as a per-place diff and the file stays
    reviewable (and under the reference-review ceiling)."""
    lines = ["{", f'"_README": {json.dumps(_README, indent=2)},', '"pois": {']
    rows = [f'"{poi_id}": {json.dumps(pois[poi_id], sort_keys=True, separators=(", ", ": "))}' for poi_id in sorted(pois)]
    lines.append(",\n".join(rows))
    lines += ["}", "}", ""]
    return "\n".join(lines)


def load_ledger(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))["pois"]


def published_records() -> list[dict]:
    """This snapshot's publishable POIs, id-bearing fields settled - THE SAME
    STEPS export_poi.main() takes before anything depends on an id, shared
    rather than reimplemented so the reconciled set and the published set
    cannot drift (read_sources' own docstring makes the same argument for
    --check). Each record also gains its inventory `fingerprint` (#672),
    read off the raw properties unify_poi kept for exactly this kind of
    composition."""
    import duckdb

    import export_poi

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    try:
        records = export_poi.read_sources(con)
        export_poi.attach_sites(records)
        distances = export_poi.load_water_distances(export_poi.WATER_DISTANCE_PATH)
        if distances:
            export_poi.attach_water_distance(records, distances)
            export_poi.synthesize_csi_water(records)
    finally:
        con.close()

    for record in records:
        properties = record.get(export_poi.RAW_PROPERTIES_KEY) or {}
        fingerprint = {
            field_name: properties[field_name]
            for field_name in FINGERPRINT_FIELDS
            if properties.get(field_name) not in (None, "")
        }
        if fingerprint:
            record["fingerprint"] = fingerprint
    return records


def real_mile_of(points: list[tuple[float, float]]) -> list[float | None]:
    """The along-trail position signal, computed the one way this repository
    computes miles: export_poi.attach_miles' own marker-calibrated axis
    (#652/#753). Batch, because the axis build is the cost and tier 2 is
    the rare path that pays it once."""
    import duckdb

    import export_poi

    centerline = export_poi.RAW_DIR / "centerline.geojson"
    markers = export_poi.RAW_DIR / "half_mile_points_from_springer.geojson"
    if not centerline.exists() or not markers.exists():
        return [None] * len(points)

    pseudo = [{"lat": lat, "lon": lon} for lat, lon in points]
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    try:
        export_poi.attach_miles(con, pseudo, centerline, markers)
    finally:
        con.close()
    return [record.get("mile") for record in pseudo]


def load_overrides(path: Path) -> dict:
    """The hand-owned file: `same` and `not_same`, each row with a reason.
    Absent is the normal state until the first refresh needs one."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(outcome: Outcome, seeded: bool) -> str:
    lines = []
    if seeded:
        lines.append(f"Seeded the ledger: {len(outcome.minted)} rows, ids exactly as published today.")
    else:
        lines.append(f"carried by key: {len(outcome.carried)}")
        lines.append(f"matched by evidence: {len(outcome.matched)}")
        for match in outcome.matched:
            lines.append(f"  = {match}")
        lines.append(f"new: {len(outcome.minted)}")
        for poi_id in outcome.minted:
            row = outcome.pois[poi_id]
            lines.append(f"  + {poi_id}  {row['poi_type']}  {row.get('name')!r}")
        lines.append(f"retired: {len(outcome.retired)}")
        for poi_id in outcome.retired:
            row = outcome.pois[poi_id]
            lines.append(f"  - {poi_id}  {row['poi_type']}  {row.get('name')!r}")
    if outcome.held:
        lines.append(f"HELD FOR REVIEW: {len(outcome.held)}")
        for held in outcome.held:
            lines.append(f"  ! {held}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify the checked-in ledger instead of writing it")
    parser.add_argument(
        "--release",
        default=None,
        help="release id (YYYY-MM-DD) stamped on new and retired rows; defaults to today (UTC)",
    )
    args = parser.parse_args(argv)

    release = args.release or datetime.now(timezone.utc).date().isoformat()
    prior = load_ledger(LEDGER_PATH)
    seeded = not prior
    records = published_records()
    print(f"{len(records)} publishable POIs against {len(live_rows(prior))} live ledger rows.")

    outcome = reconcile(prior, records, release, overrides=load_overrides(OVERRIDES_PATH), mile_of=real_mile_of)
    print(summarize(outcome, seeded))

    if outcome.held:
        print("Nothing was written - resolve the held items and re-run.", file=sys.stderr)
        return 2

    refusal = mass_retirement_refusal(outcome, prior)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2

    rendered = render(outcome.pois)
    if args.check:
        current = LEDGER_PATH.read_text(encoding="utf-8") if LEDGER_PATH.exists() else ""
        if current == rendered:
            print("Ledger is exactly what reconciliation reproduces.")
            return 0
        # NAME THE MECHANISM, not just the remedy (#811). This used to say
        # "run reconcile_poi_identity.py, review the diff, and commit it",
        # which is the right remedy and was, for a while, impossible to
        # act on: the write mode needs the raw snapshot, the snapshot lives
        # in gitignored data/raw/ on a runner mid-job, and no workflow ran
        # anything but --check. Five dispatches failed on that sentence.
        print(
            f"{LEDGER_PATH} differs from what this snapshot reconciles to.\n"
            "Re-dispatch 'Publish vector data' with 'regenerate_identity_ledger' ticked, using the "
            "SAME source inputs as this run - it runs the write mode in place of this check and "
            "uploads the new ledger and summary as the 'poi-identity-ledger' artifact. Review that "
            "diff, commit it, then publish against the reviewed ledger.\n"
            "Locally, `python reconcile_poi_identity.py` does the same thing wherever a raw snapshot "
            "already exists.",
            file=sys.stderr,
        )
        return 1

    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(rendered, encoding="utf-8")
    print(f"Ledger -> {LEDGER_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
