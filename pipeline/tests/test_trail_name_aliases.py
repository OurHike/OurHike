"""`pipeline/reference/trail_name_aliases.json` says which published spelling
means which long trail, and `client/src/map/longTrailNames.ts` is generated
from it. These guard the join itself and the two files agreeing.

WHY THE JOIN NEEDS GUARDING. Badging a line names it for a hiker, and naming
the wrong trail is worse than naming none - the asymmetry CLAUDE.md states for
every alert-shaped thing this app builds. The geographic check that produced
this file rejected 16 names that matched on spelling alone, and a row added
later without that check would look exactly like a row that had it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
ALIASES = json.loads((ROOT / "reference" / "trail_name_aliases.json").read_text())
EMBLEMS = json.loads((ROOT / "reference" / "trail_emblems.json").read_text())
REGISTRY = json.loads((ROOT / "sources.json").read_text())
CLIENT_TABLE = REPO / "client" / "src" / "map" / "longTrailNames.ts"

TRAILS = ALIASES["trails"]
EMBLEM_SLUGS = {t["slug"] for t in EMBLEMS["trails"]}
SOURCE_KEYS = {s["key"] for s in REGISTRY["sources"] if "key" in s}


def rows() -> list[tuple[str, dict]]:
    return sorted(TRAILS.items())


def test_there_are_rows_to_check():
    """The guard on the guard: every parametrised test below is vacuous over
    an empty table."""
    assert len(rows()) >= 20


@pytest.mark.parametrize("slug,row", rows())
def test_an_aliased_trail_is_one_the_catalogue_names(slug: str, row: dict):
    """A badge points at a trail this repository has a row for. An alias for
    a trail nobody catalogued is a name with nothing behind it."""
    assert slug in EMBLEM_SLUGS, f"{slug} is aliased here and absent from trail_emblems.json"
    assert row["trail"].strip()
    assert row["states"].strip()


@pytest.mark.parametrize("slug,row", rows())
def test_every_spelling_is_published_by_a_source_this_app_draws(slug: str, row: dict):
    """The key on each `published_as` block is a registered source. A spelling
    attributed to a layer nobody fetches would never match anything, and would
    read as coverage this build does not have."""
    assert row["published_as"], f"{slug}: a row with no spellings matches nothing"
    for source_key, spellings in row["published_as"].items():
        assert source_key in SOURCE_KEYS, f"{slug}: {source_key} is not a registered source"
        assert spellings, f"{slug}: {source_key} lists no spelling"
        for spelling in spellings:
            assert spelling.strip() == spelling, f"{slug}: {spelling!r} has stray whitespace"
            assert spelling.strip(), f"{slug}: an empty spelling"


def test_no_spelling_means_two_different_trails():
    """THE ONE FAILURE THAT PUTS A WRONG NAME ON A LINE. Folding is what the
    client does, so the collision has to be checked folded."""
    seen: dict[str, str] = {}
    for slug, row in rows():
        for spellings in row["published_as"].values():
            for spelling in spellings:
                folded = spelling.strip().lower()
                if folded in seen and seen[folded] != slug:
                    raise AssertionError(f"{spelling!r} is claimed by both {seen[folded]} and {slug}")
                seen[folded] = slug


def test_the_rejected_look_alikes_are_recorded_with_a_reason():
    """The rejections are the part nobody can reconstruct. Each says where the
    look-alike actually is, which is what stops it being re-added."""
    rejected = ALIASES["rejected"]
    assert len(rejected) >= 16
    for name, why in rejected.items():
        assert name.strip(), "a rejection with no name"
        assert len(why) > 40, f"{name}: a rejection has to say what the line actually is"


def test_no_rejected_spelling_crept_into_an_accepted_row():
    """A name in both blocks would mean the file contradicts itself, and the
    accepted half wins silently."""
    accepted = {
        spelling.strip().lower() for _, row in rows() for spellings in row["published_as"].values() for spelling in spellings
    }
    for name in ALIASES["rejected"]:
        for quoted in re.findall(r"'([^']+)'", name):
            assert quoted.strip().lower() not in accepted, f"{quoted!r} is recorded as rejected and is also an accepted spelling"


def _generated_pairs() -> dict[str, str]:
    """The name->slug table out of the generated client module.

    PARSED RATHER THAN GREPPED, because prettier rewrites what the generator
    emits: double quotes become single, and a key that is a plain identifier
    loses its quotes entirely, so `"appalachian trail": "at"` ships as
    `'appalachian trail': 'at'` and `"appalachian": "at"` as
    `appalachian: 'at'`. A substring test against the generator's own JSON
    passes on the day it is written and fails on the next format run.
    """
    text = CLIENT_TABLE.read_text()
    body = text.split("LONG_TRAIL_BY_NAME", 1)[1].split("}", 1)[0]
    pairs = re.findall(r"""(?:'([^']+)'|"([^"]+)"|([A-Za-z_][\w]*))\s*:\s*['"]([^'"]+)['"]""", body)
    return {(a or b or c): d for a, b, c, d in pairs}


def _generated_marker_slugs() -> set[str]:
    text = CLIENT_TABLE.read_text()
    block = text.split("SLUGS_WITH_A_STEWARD_MARKER", 1)[1].split("])", 1)[0]
    return set(re.findall(r"""['"]([a-z0-9-]+)['"]""", block))


def test_the_client_table_carries_every_spelling_this_file_holds():
    """The generated half cannot drift from the reviewed half."""
    generated = _generated_pairs()
    for slug, row in rows():
        for spellings in row["published_as"].values():
            for spelling in spellings:
                folded = spelling.strip().lower()
                assert folded in generated, f"{spelling!r} is in trail_name_aliases.json and not in {CLIENT_TABLE.name}"
                assert generated[folded] == slug, f"{spelling!r} maps to {generated[folded]} in the client and {slug} here"


def test_the_client_table_carries_nothing_this_file_does_not():
    """The other direction, which is the one that would put a badge on a line
    nobody reviewed."""
    reviewed = {
        spelling.strip().lower() for _, row in rows() for spellings in row["published_as"].values() for spelling in spellings
    }
    extra = sorted(set(_generated_pairs()) - reviewed)
    assert extra == [], f"{CLIENT_TABLE.name} claims spellings no reviewed row holds: {extra}"


def test_the_client_only_claims_a_marker_where_one_ships():
    """`longTrailHasMarker` frees the placer to use the bare-mark form, whose
    whole content is the marker - so a slug listed there without a file in the
    tree is a badge that draws nothing on a crowded map."""
    shipped = {slug for slug in REGISTRY["org_marks"]["trail_marks"] if not slug.startswith("_")}
    claimed = _generated_marker_slugs()
    assert claimed, "the marker set is empty or its shape changed"
    assert claimed <= shipped, f"claims a marker that does not ship: {sorted(claimed - shipped)}"
    assert claimed <= set(TRAILS), f"claims a marker for a trail it does not badge: {sorted(claimed - set(TRAILS))}"
