"""Fetched and derived data must not be tracked in git.

WHY THIS IS A SECURITY TEST AND NOT A TIDINESS ONE. A commit is a
publication that cannot be retracted. This repository is public, every clone
carries its whole history, and `git rm` in a later commit removes a file from
the tree while leaving it in every fork, mirror and cached pack that already
has it. So a byte committed here is a byte published permanently, before
anybody has read it.

That is exactly the wrong property for data this project fetches from
somewhere else, because the licence and the safety of that data are still
being established while it is on disk:

  - **Licence.** CONTRIBUTING.md's rule is to establish the licence before
    the bytes are in the build; several sources are still unresolved
    (opentrail.org, #98; the club PDFs, whose registry entries say
    review-only until the club answers). Committing any of them redistributes
    them under this repository's own licence, from every fork, irreversibly.
  - **Safety.** SOURCE_SURVEY.md §3b records 2,333 user-created campsites in
    ATC's own index - "the ones land managers are often trying to close" -
    and says publishing their locations would put OurHike on the wrong side
    of every partner it depends on. A file like that committed once cannot be
    unpublished.
  - **People.** Reports, photos and hiker submissions carry personal data by
    construction (features/IDENTITY_AND_PRIVACY.md). None of it belongs in a
    tree anybody can clone.

The pipeline already has the right shelf for all of it: `pipeline/data/` is
gitignored, cached between CI runs, and what hikers get is published to R2 by
`publish.py`. This test exists because the gitignore alone is a convention -
`git add -f` walks straight past it, and the mistake that prompted this test
did not need force at all. A 20,099-line derivation was written to
`pipeline/reference/`, which is NOT ignored, and committed, because that
directory holds three small checked-in files and looked like where derived
things go (#529).

The exception that directory really is, and its ceiling, are below.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Extensions that are data rather than source: something a script fetched,
#: derived, or exported. Deliberately not exhaustive - it names the shapes
#: this pipeline actually produces, and a new one is a line here.
DATA_SUFFIXES = frozenset(
    {".geojson", ".fgb", ".gpkg", ".pmtiles", ".tif", ".tiff", ".parquet", ".csv", ".sqlite", ".db", ".osm", ".zip"}
)

#: Paths that are allowed to hold data-shaped files, each for a stated
#: reason. An addition here is a decision somebody makes on purpose, which is
#: the whole point of an allowlist over a size heuristic.
ALLOWED_DATA_PATHS = (
    # Font glyphs for MapLibre. Genuinely an app asset - shipped to the
    # browser, licensed SIL OFL 1.1 with its provenance beside it - and
    # `.pbf` here means a protobuf glyph range, not an OSM extract.
    "client/public/glyphs/",
    # Vendored client assets: icons, the offline shell, anything the built
    # app serves. Same argument as the glyphs.
    "client/public/",
    # Test fixtures. Small by construction and the input to a test rather
    # than a copy of an upstream dataset - a fixture nobody can read is a
    # fixture nobody can review, which its own suite will notice first.
    "tests/fixtures/",
    "pipeline/tests/fixtures/",
    # dbt seeds (#100). The same argument as pipeline/reference/, in dbt's
    # own vocabulary: a seed is a hand-authored mapping that encodes
    # judgement, reviewed row by row - poi_type_mapping.csv is eleven lines
    # transcribed from ICON_LEGEND/OPENTRAIL_ICON_MAP/DIRECT_SOURCES and
    # held to them by pipeline/tests/test_dbt_seed_sync.py. Fetched or
    # derived data does not belong here either; load_raw.py's warehouse
    # under pipeline/data/ is where that goes, gitignored.
    "pipeline/dbt/seeds/",
)

#: The one directory of committed data this project keeps on purpose:
#: reference/ holds JOINS THAT ENCODE JUDGEMENT. A row of
#: shelter_capacity.json is somebody's decision that a hiker-list entry is a
#: particular ATC shelter, and reviewing a diff of it reviews those
#: decisions. That is worth committing, and it is a narrow thing.
REFERENCE_DIR = "pipeline/reference/"

#: And its ceiling, because the exception is what got abused. A reference
#: file is reviewable only while a human can read the rows; past that it is
#: derived data wearing a reviewed file's clothes. The file that prompted this
#: test was 20,099 lines - 1,125 crossing coordinates nobody would ever read -
#: and it now lives in data/raw/ where it belongs.
#:
#: A file that trips this is not necessarily wrong. It is a file whose author
#: has to say why a human should read that many rows, in review, out loud.
#: What follows is that being said out loud, on 2026-08-25, for the one file
#: that has ever legitimately asked (#1026).
#:
#: RAISED FROM 8,000 TO 12,000. `poi_identity.json` went from 4,267 lines to
#: 8,579 in a single publish run, and nothing about the file got looser: the
#: app started publishing for a whole state instead of a ring around New York
#: City (#1019), and water started being measured against every trail it draws
#: rather than the A.T. alone (#1016/#1023). 4,312 of its rows are new OSM
#: water points and NHD stream crossings, 4,311 of which sit on a network trail
#: with no A.T. mile at all. The ledger is one row per line, so there is no
#: formatting answer here - the line count IS the row count, which is exactly
#: what this number is meant to measure.
#:
#: The maintainer's decision (2026-08-25) is to raise it rather than split the
#: ledger, and to record what raising it costs: nobody reads 8,563 rows either.
#: What keeps the review honest meanwhile is `data/identity_review/summary.txt`,
#: which the regeneration run uploads beside the ledger and which states the
#: diff in the terms a person can actually check - new, retired, carried by
#: key, matched by evidence, with the evidence for each match.
#:
#: THE NEXT SOURCE BREAKS THIS AGAIN, and that is the honest reading of 12,000
#: rather than a bigger number: NYC_SOURCE_SURVEY.md section 5's two NJ layers
#: are 16,601 more trail segments, whose water would land in this same file. If
#: this constant is being raised a second time, the answer is probably the
#: split #1026 also proposes, not a third number.
#:
#: The other reference files are nowhere near it: water_distance.json is the
#: largest of them at ~6,400 lines (512 sites, each carrying its join evidence
#: and its refusal reason).
MAX_REFERENCE_LINES = 12_000


def tracked_files() -> list[str]:
    """Every path git actually tracks - not what is on disk.

    The distinction is the test: `pipeline/data/` is full of fetched
    geojson on any machine that has run the pipeline, and none of it is
    tracked. What matters is what a clone would carry.
    """
    result = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return [line for line in result.stdout.splitlines() if line]


@pytest.fixture(scope="module")
def tracked() -> list[str]:
    files = tracked_files()
    if not files:
        raise AssertionError("git ls-files returned nothing - this test would assert nothing")
    return files


def test_no_pipeline_data_directory_is_tracked(tracked):
    """`pipeline/data/` is gitignored, and this is the check that the ignore
    was not walked past. `git add -f` is one keystroke, and a fetched layer
    committed by accident is an upstream dataset republished under this
    repository's licence from every fork that pulls it."""
    committed = [path for path in tracked if path.startswith("pipeline/data/")]

    assert committed == [], (
        "pipeline/data/ is fetched and derived data and must never be tracked - it is "
        f"gitignored, cached in CI, and published to R2 by publish.py. Tracked: {committed[:5]}"
    )


def test_no_data_shaped_file_is_tracked_outside_the_allowlist(tracked):
    """The general rule, because the next mistake will not be in data/.

    Anything a script fetched, derived or exported belongs in `data/` and
    reaches hikers through R2. A `.geojson` in the tree is either an app
    asset (allowlisted, with its reason) or a dataset somebody published
    permanently without meaning to.
    """
    offenders = [
        path
        for path in tracked
        if Path(path).suffix.lower() in DATA_SUFFIXES and not any(path.startswith(allowed) for allowed in ALLOWED_DATA_PATHS)
    ]

    assert offenders == [], (
        "These look like fetched or derived data committed to the repository. Data belongs "
        "in pipeline/data/ (gitignored, cached, published to R2) - a commit is a publication "
        "that cannot be retracted, and the licence and safety of an upstream dataset are "
        f"still being established while it sits on disk. If one of these is genuinely an app "
        f"asset, add its directory to ALLOWED_DATA_PATHS with the reason: {offenders}"
    )


def test_reference_files_stay_small_enough_for_a_human_to_review(tracked):
    """The exception, kept narrow.

    reference/ is committed because a diff of it reviews the judgement each
    row encodes. That argument holds only while somebody actually reads the
    rows - and it was used to justify committing 20,099 lines of derived
    geometry, which nobody read (#529). The ceiling is not a storage limit;
    it is the point at which the justification stops being true.
    """
    oversized = []
    for path in tracked:
        if not path.startswith(REFERENCE_DIR):
            continue
        lines = (REPO_ROOT / path).read_text(encoding="utf-8").count("\n")
        if lines > MAX_REFERENCE_LINES:
            oversized.append(f"{path} ({lines:,} lines)")

    assert oversized == [], (
        f"A file in {REFERENCE_DIR} is past {MAX_REFERENCE_LINES:,} lines, which is where "
        "'committed so the judgement in it can be reviewed' stops being true - nobody reviews "
        "that many rows. Either it is derived data that belongs in pipeline/data/ and R2, or "
        f"say in review why a human should read this many rows: {oversized}"
    )
