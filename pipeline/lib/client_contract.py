"""What the client asks for, and how much of it a launch may fetch whole,
read out of the client's own source.

Two contracts between this pipeline and client/src/lib, both read rather than
restated, so the two ends cannot drift apart unseen:

  - check 2's key contract: every key client/src/lib/config.ts declares, with
    its `@release` word (`expected_client_keys`);
  - check 22, the launch budget: no artifact a phone fetches whole may be
    bigger than client/src/lib/artifactBudget.ts's
    LAUNCH_ARTIFACT_BUDGET_BYTES (`check_launch_budget`).

WHY APART FROM verify_release.py, which was their home until 2026-10-15. That
battery reads a release over HTTP and imports requests and pmtiles; check 22
needs neither, since it weighs a manifest's `size_bytes` against the client's
own number. And check 22 now runs where verify_release.py does not: UA's
phones were handed release 2026-10-03-2 and its 41,216,145-byte
network_overview.geojson although verify-release.yml, the only place check 22
ran, is a dispatch-only promotion gate that a UA publish never passes through
(Measured 2026-10-15 against UA's manifest; review 5528343443 on PR #1805).
So it also runs in:

  - publish.py, which refuses to stage a release folder carrying such an
    artifact (`refuse_over_launch_budget`);
  - the deploy guards in ua.yml and pages.yml, which refuse a build whose
    pinned release carries one, and pr-preview.yml, which says so on the
    preview. They run .github/scripts/check_launch_budget.py on a runner's
    bare python3, with nothing installed.

So this module imports nothing outside the standard library, and
pipeline/tests/test_client_contract.py holds it to that. verify_release.py
imports back the names its battery and its tests use, so they read them where
they always have.
"""

from __future__ import annotations

import re
from pathlib import Path

CLIENT_LIB = Path(__file__).resolve().parents[2] / "client" / "src" / "lib"

OK = "ok"
FAILED = "failed"
SKIPPED = "skipped"
# The check ran, answered, and the answer is worth a human's eye without being
# a reason to hold a release (#1173). Distinct from SKIPPED, which means the
# check could not run at all - `--strict` escalates that one and deliberately
# not this one, because escalating "we looked and it is probably fine" is how a
# gate goes back to crying wolf.
WARN = "warn"


def report(check: int, key: str, state: str, detail: str) -> dict:
    """One line of the verdict: which check, about which key, and what it found."""
    return {"check": check, "key": key, "state": state, "detail": detail}


# ---------------------------------------------------------------------------
# What the CLIENT will ask for. Read out of the client's own source rather
# than restated, per DATA_RELEASES.md §3 check 2: a tier the app offered and
# the bucket lacked has already happened once (publish.py:65-67).
#
# Parsing TypeScript from Python is not lovely, and the alternative is worse -
# a hand-kept copy here is a second home for the contract, and the whole
# failure being guarded against is the two disagreeing. The regexes are narrow
# and `expected_client_keys` raises rather than returning a short list, so a
# rename in config.ts fails this loudly instead of quietly checking fewer keys.
#
# UNTIL #1048 IT READ FOUR NAMES OUT OF A FILE DECLARING SEVENTEEN, and the
# gap was invisible from here: the four matched, nothing raised, and of those
# seventeen keys check 2 reached exactly one - `TRAILS_KEY`. (It asked after
# thirteen keys in all; the other twelve are the POI types and archive tiers,
# which are generated names rather than declared ones.) A release missing
# `trail_graph.json`, `club_sections.json`, `highlights.json`,
# `trails_overview.geojson`, `stewards.json`, `retired_poi.geojson`,
# `nearby_trails.geojson` and the two graph companions passed it (measured
# 2026-08-26, #1048's own table). Now every `export const *_KEY = '...'` is
# read, and each one carries an `@release` declaration beside it.
#
# WHAT THAT DECLARATION ANSWERS, because the obvious reading is the wrong one.
# It is NOT "does the app survive this artifact's absence" - measured against
# `main` on 2026-09-05, sixteen of the seventeen survive it deliberately, each
# through its own fetch path (`fetchOptionalArtifact` for seven of them,
# trailOverview.ts:56, trailGraphData.ts:193 and nearbyTrailData.ts:245 for the
# rest), because a hiker holding a release exported before an artifact existed
# must not be shown an error. A declaration on that axis would SKIP every key
# this check exists to catch. The phone structurally cannot tell "this release
# predates it" from "this release should have it", and this script is the only
# thing that can, because it knows the checkout it was run from.
#
# So it answers #940's invariant instead - can an exporter in THIS CHECKOUT
# write it - which is the half PR #1108 deliberately left ("the bucket-contents
# half is still worth having and is not this"). `publish.py` can write all
# seventeen, so that alone would be no discriminator either; what separates
# them is that seven sit behind a `reaches_hikers` licence gate and one behind
# whether a sheet's cut ran, and those are conditions no reading of the code
# can evaluate.
#
# THE CONTRACT IS BETWEEN THIS CHECKOUT AND THE RELEASE IT BUILT. Pointed at an
# older release, this will fail keys that release's checkout could not write -
# that is the check working rather than a false positive, and it is how #1048
# was found. verify-release.yml is dispatch-only for exactly this reason: a
# person asks it about a candidate they are deciding whether to promote.
#
# @unvalidated - a licence-gated key reports SKIPPED whether or not its gate is
# actually shut, so a graph missing while every steward says `reaches_hikers:
# true` reads the same as one held back. Resolving it needs the artifact ->
# steward mapping, which today exists only in the generated manifests under
# `pipeline/data/` and so is unavailable to a gate run from a clean checkout
# against a public URL. `pipeline/sources.json` is checked in and would be half
# of it; the other half is what would settle this.
# ---------------------------------------------------------------------------

#: A release must carry this key, or check 2 fails.
REQUIRED = "required"
#: publish.py can decline to write this key for a reason outside the code, so
#: its absence is a declaration rather than a defect - a named SKIPPED.
OPTIONAL = "optional"

_KEY_DECLARATION = re.compile(r"^export const (\w+_KEY)\s*=\s*'([^']+)'", re.MULTILINE)
_RELEASE_TAG = re.compile(rf"@release\s+({REQUIRED}|{OPTIONAL})\b")


def read_client_file(name: str) -> str:
    return (CLIENT_LIB / name).read_text(encoding="utf-8")


def _declared_keys(source: str) -> dict[str, str]:
    """Each `*_KEY` constant in config.ts, mapped to its `@release` word.

    A key's declaration is the one tag between the previous key and this one,
    which is that key's own comment block and nothing else. Exactly one, so a
    tag left behind by a copied comment fails here rather than quietly
    declaring the wrong thing about the wrong artifact.
    """
    declared: dict[str, str] = {}
    cursor = 0
    for match in _KEY_DECLARATION.finditer(source):
        name, key = match.group(1), match.group(2)
        tags = _RELEASE_TAG.findall(source[cursor : match.start()])
        cursor = match.end()
        if len(tags) != 1:
            found = f"{len(tags)} of them" if tags else "none"
            raise ValueError(
                f"{name} in client/src/lib/config.ts carries {found} where it needs exactly one "
                f"`@release {REQUIRED}` or `@release {OPTIONAL}` line. Every key the client can "
                "request has to say whether a release built from this checkout must carry it - "
                "that question is what check 2 asks, and an artifact added without answering it "
                "is the gap #1048 found."
            )
        declared[key] = tags[0]
    return declared


def expected_client_keys(config_ts: str | None = None) -> dict[str, str]:
    """Every object key the client is built to request, and what it is owed.

    Maps key -> REQUIRED or OPTIONAL. Iterating it yields the keys, which is
    what most callers want; the values are what check 2 grades against.
    """
    source = config_ts if config_ts is not None else read_client_file("config.ts")

    poi_types = re.search(r"POI_TYPES\s*=\s*\[([^\]]+)\]", source)
    poi_pattern = re.search(r"poiKey\([^)]*\)[^{]*\{\s*return\s*`([^`]+)`", source)
    archives = re.findall(r"^\s*(?:light|standard|fine):\s*'([^']+)'", source, re.MULTILINE)
    declared = _declared_keys(source)

    if not (poi_types and poi_pattern and archives and declared):
        raise ValueError(
            "could not read the key contract out of client/src/lib/config.ts. "
            "It has been restructured, and this check must be updated rather than "
            "left matching fewer keys than the client asks for."
        )

    types = re.findall(r"'([^']+)'", poi_types.group(1))
    # The generated names carry no declaration of their own and need none:
    # publish.py writes every `poi_<type>.geojson` from one ungated manifest
    # (:706) and every archive is a file on disk (:849), so a type or a tier
    # the client offers and the release lacks is the plain failure this check
    # has always called it. A withdrawn tier is still weakened below.
    keys = dict.fromkeys(
        [poi_pattern.group(1).replace("${type}", poi_type) for poi_type in types] + archives,
        REQUIRED,
    )
    return {**declared, **keys}


def launch_artifact_budget(artifact_budget_ts: str | None = None) -> int:
    """How many decoded bytes the client will fetch whole, from its own declaration.

    `client/src/lib/artifactBudget.ts` is where the number lives and why
    (#1254): the app declines an artifact the manifest says is bigger than
    this, and the day that guard was written was the day a promotion carried
    a 228.8 MB `nearby_trails.geojson` and a 78.6 MB `trail_graph.json` to
    every phone - a crashed map and a frozen first page. Read out of the
    client's source for the reason `expected_client_keys` reads config.ts: a
    copy here would be a second home for the contract, and the two drifting
    apart is the failure this check exists to catch.
    """
    source = artifact_budget_ts if artifact_budget_ts is not None else read_client_file("artifactBudget.ts")
    # Anchored to the end of its line, so an expression (`32 * 1024 * 1024`) is a
    # restructuring this cannot follow rather than a budget of 32 bytes.
    found = re.search(r"LAUNCH_ARTIFACT_BUDGET_BYTES\s*=\s*([\d_]+)\s*$", source, re.MULTILINE)
    if not found:
        raise ValueError(
            "could not read LAUNCH_ARTIFACT_BUDGET_BYTES out of client/src/lib/artifactBudget.ts. "
            "It has been restructured, and this check must be updated rather than left "
            "weighing nothing."
        )
    return int(found.group(1).replace("_", ""))


# What is read by byte range rather than fetched whole. Everything else
# publish.py gzips and the client reads entire - `response.arrayBuffer()` or
# `.json()` - so check 22's budget applies to every key NOT ending in one of
# these. The same literal lib/dataManifest.ts keeps as STORED_UNCOMPRESSED,
# rather than an import from content_types.py, so the two ends of the
# contract name the same files by the same rule.
RANGE_READ_SUFFIXES = (".pmtiles", ".fgb")


# The per-cell graph shards (cut_trail_graph.py): fetched whole and parsed,
# so weighed, but derived on the phone from `trail_graph_cells.json` rather
# than declared one by one in config.ts. The four halves, any cell name.
_GRAPH_CELL_SHARD = re.compile(r"^trail_graph(_geometry|_elevation|_profile)?_cell_[ns]\d{2}[ew]\d{3}\.json$")

# One hike's prose (#1473, export_suggested_hikes.py's DETAIL_KEY): fetched
# whole by lib/useHikeDetail.ts when somebody opens that hike, and named per
# hike rather than declared in config.ts - the same reason the graph shards
# need a pattern here.
#
# WEIGHED RATHER THAN SKIPPED, and the budget is not the only ceiling it is
# standing in for. A detail is kept in the conditions cache, whose
# MAX_CACHED_BYTES DELETES an oversize artifact rather than trimming it, so a
# runaway description reaches a phone, fails to keep, and refetches on every
# open forever. Left unmatched here, all 201 of these would have SKIPPED with
# a reason that is not true of them - and `--strict` counts a skip as a
# failure.
_SUGGESTED_HIKE_DETAIL = re.compile(r"^suggested_hikes_detail_\d+\.json$")


def fetched_whole_by_the_client(key: str, client_keys: set[str]) -> bool:
    """Whether some phone running the current client fetches `key` entire -
    the artifacts check 22 weighs. Declared keys, plus the two families the
    client names at runtime from an index rather than declaring one by one:
    the graph shards, and one hike's prose."""
    return key in client_keys or _GRAPH_CELL_SHARD.match(key) is not None or _SUGGESTED_HIKE_DETAIL.match(key) is not None


def check_launch_budget(
    manifest: dict, budget: int | None = None, client_keys: set[str] | frozenset[str] | None = None
) -> list[dict]:
    """Check 22: no whole-fetched artifact is bigger than the client will load.

    The client fetches every text artifact entire and parses it - the junction
    graph on the main thread - and on 2026-09-07 a promotion whose gate 6 was
    green carried a 78,595,556-byte `trail_graph.json` and a 228,820,578-byte
    `nearby_trails.geojson` to production: the first froze the main thread
    for ten seconds, the second crashed the renderer (#1254). Check 15 had
    looked straight at the cause - #1231's nationwide USFS features - and
    documented it as an exception, and nothing weighed the result.

    The client now declines an artifact over `LAUNCH_ARTIFACT_BUDGET_BYTES`
    (client/src/lib/artifactBudget.ts), so a phone survives, but without the
    file: UA's release 2026-10-03-2 reached every UA phone with a
    41,216,145-byte `network_overview.geojson`, and the opening map drew the
    A.T. alone (review 5528343443 on PR #1805, Measured 2026-10-15). So this
    runs, against the same number read from the same file, wherever a release
    is about to reach a phone: publish.py before it stages a release folder
    (`refuse_over_launch_budget`), the deploy guards before a build that pins
    one ships (.github/scripts/check_launch_budget.py), and verify_release.py
    before a promotion. One OK row for the whole family rather than one per
    artifact, because a hundred identical passes are where the one failure
    hides; a failure or a skip names its artifact.

    A text artifact with no `size_bytes` is a SKIP, never a pass: it is exactly
    the artifact the client cannot weigh before fetching either.

    WEIGHED: WHAT THE CURRENT CLIENT FETCHES WHOLE, AND ONLY THAT (#1257). The
    keys client/src/lib/config.ts declares (`expected_client_keys`), plus the
    per-cell graph shards it derives from the cell index rather than declaring
    one by one (`fetched_whole_by_the_client`). An artifact nothing in the
    current client requests - `trail_graph.json` and `nearby_trails.geojson`
    since the tiles and the cells replaced them - is a SKIP with the reason
    named, not a failure: it stays in the bucket as the cut's input and for
    older clients, and weighing it would keep the gate red on a file no
    phone this release ships will ever parse. The manifest merge being
    additive-only, nothing else could ever let this check go green again.
    """
    budget = launch_artifact_budget() if budget is None else budget
    client_keys = set(expected_client_keys() if client_keys is None else client_keys)
    reports = []
    weighed: list[tuple[int, str]] = []
    for key, entry in sorted(manifest["artifacts"].items()):
        if key.endswith(RANGE_READ_SUFFIXES):
            continue
        if not fetched_whole_by_the_client(key, client_keys):
            reports.append(
                report(
                    22,
                    key,
                    SKIPPED,
                    "not fetched whole by the current client (client/src/lib/config.ts declares no key for it "
                    "and it is no cell shard), so its size cannot reach a phone this release ships; left in "
                    "the bucket as a cut's input and for older clients",
                )
            )
            continue
        size = entry.get("size_bytes")
        if not isinstance(size, int) or isinstance(size, bool):
            reports.append(
                report(
                    22,
                    key,
                    SKIPPED,
                    "no size_bytes published, so neither this check nor the client can weigh it before it is fetched whole",
                )
            )
            continue
        if size > budget:
            reports.append(
                report(
                    22,
                    key,
                    FAILED,
                    f"{size:,} bytes decoded is over the {budget:,}-byte launch budget the client enforces "
                    f"(client/src/lib/artifactBudget.ts, #1254): a phone declines it, and before the budget "
                    f"existed a phone fetching it whole froze or crashed",
                )
            )
            continue
        weighed.append((size, key))
    if weighed:
        largest, largest_key = max(weighed)
        detail = f"{len(weighed)} within the {budget:,}-byte launch budget; largest {largest:,} bytes ({largest_key})"
    else:
        detail = "no artifact in this release is fetched whole, so there is nothing to weigh"
    reports.append(report(22, "whole-fetched artifacts", OK, detail))
    return reports
