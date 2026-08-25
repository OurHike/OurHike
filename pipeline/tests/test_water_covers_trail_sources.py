"""Registering a trail-line source must not be able to put a trail on the map
with silently absent water (#1017).

THE FAILURE THIS EXISTS TO PREVENT, WHICH HAS ALREADY HAPPENED FOUR TIMES.

Registering a trail-line source in sources.json is deliberately cheap, and
three separate exports pick one up with no code change at all:
`export_trails.load_line_sources` and `export_nearby_trails.network_line_sources`
both key off `blaze_field`/`blaze_default`, and `fetch_elevation.network_extent`
pulls the DEM cells a new source needs straight off the published artifact
(#1011). That is the right design, and it has a cost: **water does not follow,
and nothing said so.** `oprhp_trails`, `nynjtc_long_path`,
`nynjtc_highlands_trail` and `mohonk_trails` were each registered, drawn, and
shipped to hikers over three pull requests with no water source of either
hydrography anywhere near them, and every check stayed green -
**#1016 - No trail outside the A.T. gets an OSM or NHD water source, though the
map promises water on every trail on screen**.

WHAT THIS ASSERTS, AND THE ONE THING IT DELIBERATELY DOES NOT.

It does NOT assert that every trail has water. That would be red today and
would amount to asserting #1016's whole feature from a test file. What it
asserts is that the DECISION is mandatory - the shape `reaches_hikers` already
uses one file over, where `export_sources.py` refuses to run if any entry lacks
the field "so a newly registered source cannot reach a hiker's screen by
defaulting into it" (sources.json, `reaches_hikers_comment`). A source may be
covered by the water build, or recorded below as a known gap against the issue
tracking it. It may not be neither, and it may not be both.

WHY THE TWO SIDES ARE READ FROM THE CODE RATHER THAN LISTED HERE.

Both halves are derived, so neither can go stale against what actually runs:
the trails come through the same two loaders the exports use, and the coverage
comes out of `build_osm_water_reach.LINE_SOURCES` and
`fetch_trail_water.CENTERLINE_PATH` - the constants that literally decide which
geometry a water point is measured against. A hand-written list on either side
would be a fifth thing to forget, which is the failure already being guarded.

The join between them is `fetch_all.py`'s own naming rule: each fetched source
is written to `data/raw/<key>.geojson` (fetch_all.py:60), so a filename stem in
the water build IS a registry key.

THIS GUARD CONVERTS ITSELF WHEN #1016 LANDS. Point the gate's line union at the
published network artifact - the fix #1016 proposes, in #1011's shape - and
`NETWORK_ARTIFACT_STEM` below marks every network source covered, at which
point `test_no_recorded_gap_survives_the_water_build_reaching_it` goes red
until the ledger is emptied. A ledger that outlives the gap it describes is the
failure CLAUDE.md names for stale issue claims, and it applies here too.
"""

import json
from pathlib import Path

import pytest

import build_osm_water_reach
import export_nearby_trails
import export_trails
import fetch_trail_water

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "sources.json"

# The issue every recorded gap has to point at, so `grep -rn 1016 pipeline/`
# answers "what has no water" in one command. Its title is in the docstring
# above rather than repeated four times below.
TRACKING_ISSUE = "#1016"

# `export_nearby_trails.py` writes every external organization's lines into one
# artifact, so unlike the A.T.'s per-source files there is no per-key filename
# for the water build to name. Its stem appearing among the gate's line sources
# is therefore what "the water build measures against the network" looks like -
# see the last paragraph of the module docstring.
NETWORK_ARTIFACT_STEM = "nearby_trails"

# The registered trail-line sources the water build does not reach, each with
# what a hiker loses by it. Delete an entry when the water build reaches that
# source; add one only with an issue behind it.
#
# All four are network sources and all four fail the same way, at
# build_osm_water_reach.measure_distances: an OSM spring beside one of their
# trails is fetched (New York is in export_basemap.AT_STATES) and survives the
# corridor clip, then is refused by a gate whose union holds ATC's centerline,
# ATC's side trails and ATC's shelters and campsites - so the rejection reads
# "no trail, side trail, shelter or campsite within 5 miles" for a spring that
# may be fifty feet from a trail somebody is standing on. Crossings are worse
# than gated: fetch_trail_water.py intersects streams with ATC's centerline
# alone, so a stream crossing one of these trails is geometry it never asks
# about.
KNOWN_UNCOVERED = {
    "oprhp_trails": f"{TRACKING_ISSUE}: 16,641 statewide segments, none measured against any water",
    "nynjtc_long_path": f"{TRACKING_ISSUE}: the Long Path's sections, none measured against any water",
    "nynjtc_highlands_trail": f"{TRACKING_ISSUE}: the Highlands Trail's sections, none measured against any water",
    "mohonk_trails": f"{TRACKING_ISSUE}: Mohonk Preserve's trails and carriage roads, none measured against any water",
}


def registered_trail_line_sources(sources_path: Path) -> dict[str, str]:
    """`key -> which export draws it`, through the exports' own loaders.

    The union is every trail line this app draws: `export_trails.py` clips the
    A.T.'s two line sources to the 30-mile corridor, `export_nearby_trails.py`
    takes every external entry carrying the same blaze marker. One marker, two
    exports, `kind` deciding which - and calling both is what makes this list
    unable to disagree with what a hiker sees.
    """
    registry = json.loads(sources_path.read_text(encoding="utf-8"))
    drawn = {source["key"]: "A.T." for source in export_trails.load_line_sources(sources_path)}
    drawn.update({source["key"]: "network" for source in export_nearby_trails.network_line_sources(registry)})
    return drawn


def water_covered_sources(sources_path: Path, line_sources: dict[str, str] | None = None) -> frozenset[str]:
    """The registry keys whose lines a water point is actually measured against.

    Read off the two constants that decide it rather than restated:
    `build_osm_water_reach.LINE_SOURCES` is the OSM reach gate's line union, and
    `fetch_trail_water.CENTERLINE_PATH` is the only geometry its stream
    intersections ever touch. Filename stems are registry keys (see the module
    docstring), except the network artifact, which stands for all of its sources
    at once.

    `line_sources` overrides the first of those, and exists so the tests of this
    file's own machinery can pin what they are measuring against. They would
    otherwise change meaning the day #1016 widens the real constant - a
    mechanism test that quietly stops testing the mechanism.
    """
    if line_sources is None:
        line_sources = build_osm_water_reach.LINE_SOURCES
    stems = {Path(filename).stem for filename in line_sources.values()}
    stems.add(fetch_trail_water.CENTERLINE_PATH.stem)

    covered = set(stems)
    if NETWORK_ARTIFACT_STEM in stems:
        registry = json.loads(sources_path.read_text(encoding="utf-8"))
        covered.update(source["key"] for source in export_nearby_trails.network_line_sources(registry))
    return frozenset(covered)


def unaccounted_for(sources_path: Path, ledger: dict[str, str], line_sources: dict[str, str] | None = None) -> dict[str, str]:
    """`key -> which export draws it`, for every trail-line source that is
    neither reached by the water build nor recorded as a known gap."""
    covered = water_covered_sources(sources_path, line_sources)
    drawn = registered_trail_line_sources(sources_path)
    return {key: drawn_by for key, drawn_by in drawn.items() if key not in covered and key not in ledger}


def write_registry(tmp_path: Path, *sources: dict) -> Path:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"_comment": "synthetic", "sources": list(sources)}), encoding="utf-8")
    return path


def a_new_org(**overrides) -> dict:
    """The shape a fifth organization's trail layer arrives in - the marker keys
    are all that matter here, and they are the ones both exports key off."""
    source = {
        "key": "dec_catskills_trails",
        "title": "DEC Catskills Trails",
        "kind": "external_arcgis_layer",
        "url": "https://example.test/dec",
        "blaze_field": "Blaze",
        "reaches_hikers": True,
    }
    source.update(overrides)
    return source


# What the OSM reach gate's line union holds today, pinned so the tests of this
# file's machinery keep testing machinery after #1016 widens the real one.
AT_ONLY = {"centerline": "centerline.geojson", "side_trail": "side_trails.geojson"}

# And what #1016 proposes it become - one artifact standing for every network
# source, in #1011's shape rather than a key per organization.
WITH_THE_NETWORK = {**AT_ONLY, "network_trail": f"{NETWORK_ARTIFACT_STEM}.geojson"}


class TestTheGuardItself:
    """Driven with synthetic registries, because the point of these is that the
    check fires - and a check only ever run against a registry it passes on is
    a check nobody has seen work."""

    def test_a_newly_registered_org_is_unaccounted_for(self, tmp_path):
        # The whole reason this file exists: registering a source is a
        # one-entry change that puts a trail on a hiker's map, and nothing
        # about it forces anybody to think about water.
        path = write_registry(tmp_path, a_new_org())

        assert unaccounted_for(path, KNOWN_UNCOVERED, AT_ONLY) == {"dec_catskills_trails": "network"}

    def test_recording_the_gap_accounts_for_it(self, tmp_path):
        path = write_registry(tmp_path, a_new_org())

        ledger = {**KNOWN_UNCOVERED, "dec_catskills_trails": f"{TRACKING_ISSUE}: not yet"}

        assert unaccounted_for(path, ledger, AT_ONLY) == {}

    def test_pointing_the_gate_at_the_network_artifact_covers_every_network_source(self, tmp_path):
        """#1016's fix, simulated - and the reason the ledger is not the only
        way out of this guard.

        One artifact in the gate's union covers every source that publishes
        into it, including ones registered later, which is what makes the fix a
        fix rather than four more entries to maintain.
        """
        path = write_registry(tmp_path, a_new_org())

        assert unaccounted_for(path, ledger={}, line_sources=WITH_THE_NETWORK) == {}
        assert "dec_catskills_trails" in water_covered_sources(path, WITH_THE_NETWORK)

    def test_a_source_carrying_no_blaze_marker_is_not_a_trail_line(self, tmp_path):
        # OPRHP's facilities points and its park polygons are registered and
        # external and are not trail lines. Neither export draws them and
        # neither does this - a water gate has nothing to say about a park
        # boundary, and demanding a decision about one would train the next
        # author to record entries to make a test stop complaining.
        not_a_line = {
            "key": "oprhp_park_polygons",
            "title": "NYS Parks Unit Boundaries",
            "kind": "external_arcgis_layer",
            "url": "https://example.test/oprhp-units",
            "reaches_hikers": False,
        }
        path = write_registry(tmp_path, not_a_line)

        assert unaccounted_for(path, KNOWN_UNCOVERED, AT_ONLY) == {}

    def test_the_at_line_sources_are_covered_without_being_recorded(self, tmp_path):
        # The other direction: the corridor's own lines ARE what the water
        # build measures against, so they must never need a ledger entry.
        # This is what stops the guard from being satisfiable by simply
        # recording everything.
        centerline = {"key": "centerline", "title": "A.T. Centerline", "blaze_default": "white", "reaches_hikers": True}
        path = write_registry(tmp_path, centerline)

        assert unaccounted_for(path, ledger={}, line_sources=AT_ONLY) == {}


class TestTheRealRegistry:
    def test_every_trail_line_source_is_covered_or_a_recorded_gap(self):
        """The guard, on the file that ships.

        Failing here means a trail-line source was registered and nobody said
        what happens to water on it. Two ways out, and picking is the point:
        wire the water build to it (#1016 has the shape - point
        `build_osm_water_reach.LINE_SOURCES` at the published network artifact
        rather than adding a key), or add it to KNOWN_UNCOVERED above with the
        issue that tracks the gap.
        """
        missing = unaccounted_for(SOURCES_PATH, KNOWN_UNCOVERED)

        assert missing == {}, (
            f"registered trail lines with no water decision: {sorted(missing)} - "
            f"either the water build measures against them or KNOWN_UNCOVERED records why not"
        )

    def test_the_enumeration_is_not_empty(self):
        """Anti-vacuity. Every assertion in this class passes trivially if the
        loaders return nothing - a renamed marker key, a moved sources.json -
        and a guard that passes because it found no trails is the same as no
        guard."""
        drawn = registered_trail_line_sources(SOURCES_PATH)

        assert "centerline" in drawn, "the A.T. itself is not in the enumeration, so nothing else can be trusted to be"
        assert sum(1 for kind in drawn.values() if kind == "network") >= 4, "the four network sources of 2026-08-25"

    def test_the_water_build_still_measures_against_the_corridor(self):
        """The coverage side, likewise anti-vacuous: if this ever empties, every
        source becomes 'uncovered' and the ledger silently becomes the whole
        answer."""
        assert {"centerline", "side_trails"} <= water_covered_sources(SOURCES_PATH)

    @pytest.mark.parametrize("key", sorted(KNOWN_UNCOVERED))
    def test_a_recorded_gap_is_still_a_registered_source(self, key):
        """A ledger entry for a source nobody registers any more is a claim
        about nothing, and it makes the ledger read longer than the gap is."""
        assert key in registered_trail_line_sources(SOURCES_PATH), f"{key} is recorded as uncovered but is not registered"

    @pytest.mark.parametrize("key", sorted(KNOWN_UNCOVERED))
    def test_no_recorded_gap_survives_the_water_build_reaching_it(self, key):
        """The self-conversion. When #1016 lands, this is what goes red and
        makes somebody delete the entry rather than leaving a stale 'no water
        here' beside a source that now has some."""
        assert key not in water_covered_sources(SOURCES_PATH), f"{key} now has water - delete its KNOWN_UNCOVERED entry"

    @pytest.mark.parametrize("key", sorted(KNOWN_UNCOVERED))
    def test_a_recorded_gap_names_the_issue_tracking_it(self, key):
        """A reason with no issue behind it is a shrug. The grep in the module
        docstring is the thing this keeps working."""
        assert TRACKING_ISSUE in KNOWN_UNCOVERED[key]
