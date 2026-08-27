"""Export the trail lines OTHER organizations maintain, for the map to draw
behind the chosen trail (#950, features/NEARBY_TRAILS.md).

export_trails.py's subject is the A.T.: two ATC sources, clipped to a 30-mile
corridor around ATC's own centerline. This module's subject is everything else
already on the ground a hiker is standing on - NYS OPRHP's statewide layer,
NYS DEC's statewide hiking layer, NYNJTC's two public extracts and Mohonk
Preserve's own, with the NJ layers still to come when
pipeline/NYC_SOURCE_SURVEY.md's next verdicts are acted on. Different sources,
a different extent, and a different licence footing, which is why it is a
second export rather than a branch inside the first.

AND NO EXTENT OF ITS OWN, SINCE #1019. This module used to clip everything to
a bounding box around New York City - NYC_SOURCE_SURVEY.md §1's proposed
"ring", which that section had left with two edges explicitly open. The
maintainer closed both on 2026-08-25, in these words:

    "There shouldnt be a ring around NYC. Include all of DEC, NYNJTC & NYSP.
     Don't limit data from orgs based on geography."

So every filter below is something the SOURCE says about a trail - is it
walkable, is it open, does another organization own the route - and none of
them is where the trail is. What that bought, measured 2026-08-25 by running
this export either side of the change against the same fetched layers:

    4,002 features -> 21,805, and 5.4 MB -> 23.5 MB on disk (1.7 -> 7.3 MB
    gzipped, which is what a phone actually pulls). #1019 flags that
    download rather than solving it: features/NEARBY_TRAILS.md §9 carries
    the number into #552's offline-unit decision, which is where a
    per-region cut would be argued and is not this module's to take.

    NYS Parks: 3,618 of their 16,641 statewide segments -> 16,187. NYNJTC's
    Long Path: 33 of 43 sections -> all 43, so it no longer stops at a
    section boundary in the Catskills while NYNJTC's own line runs on to
    43.23°. DEC, registered by the same change: the ring would have kept 418
    of its 5,286 rows, and 5,224 ship.

WHAT THE CLIENT DOES WITH THIS, AND WHY THE PROPERTY NAMES ARE NOT NEGOTIABLE

Nothing here invents a display vocabulary. Every property below is one the
client already reads off a trail feature, so a line from this artifact is drawn
by the SAME expressions the A.T. is drawn by:

  `source`        map/style.ts keys line width and draw order off it, and
                  map/nearbyTrails.ts keys GHOSTING off it - a source outside
                  CHOSEN_SYSTEM_SOURCES draws at NEARBY_TRAIL_OPACITY. Every
                  key this module writes is outside that list, which is how
                  these lines end up dimmed without anybody passing a flag.
  `blaze_color`   the normalized palette member map/style.ts paints.
  `name`          map/trailLabels.ts's label, dimmed with its own line.
  `trail_status`  lib/closureStyle.ts's LONG_TERM_CLOSED_FILTER compares this,
                  downcased, against "closed" and draws the barred band.
  `id`            the feature identity map/lineTaps.ts hands the sheet.

THE THREE FILTERS, AND THE EVIDENCE UNDER EACH

Counts below carry their own date. The 2026-08-24 ones were measured against
the layers fetch_external_layers.py had just fetched, re-running the census
spike_nyc_trails.py first ran on 2026-08-18; the 2026-08-25 ones were measured
by #1019's re-run, which is also the first run of this export over DEC's layer
and over the whole of OPRHP's. Where two dates disagree the newer is written
down.

1. HIKING ONLY - the maintainer's decision, 2026-08-18 ("Only keep hiking
   trails for now... It's OurHike, not OurBike"). A source declaring a
   `foot_field` keeps only the rows whose value is in its own `foot_allowed`
   set; a source with no use flags at all keeps every row, because NYNJTC and
   Mohonk publish hiking trails and nothing else. Statewide, OPRHP's Foot
   column is a clean two-value domain (Y 16,441 / N 200), so its allowed set
   is the default {"Y"} and the 200 are what this filter drops - it dropped 53
   while the ring was on, because the other 147 were outside the box before
   this filter ever saw them.

   WHY THE ALLOWED SET IS PER-SOURCE RATHER THAN ONE CONSTANT, which is the
   shape #1019 found when DEC arrived. DEC's FOOT is the same five-code
   CORRIDOR USE domain OPRHP's is (Y/N/U/M/-99, read off the live field
   metadata 2026-08-25) and its live values are not: over all 5,286 rows of
   DEC's own Hiking Trails layer, 4,050 read `Y` and 1,236 read `M` - DEC's
   code for MAINTAINED - and nothing reads N, U or -99. A single {"Y"} would
   have dropped 23% of the layer DEC itself publishes as hiking trails, which
   is the opposite of what a hiking-only filter is for. sources.json's
   `dec_hiking_trails` entry carries what `M` is read as, and what would
   settle it.

2. STATUS - the maintainer's decision, 2026-08-18, taken with the statewide
   counts in front of them: `Open` ships, `Closed` SHIPS DRAWN AS CLOSED (so
   somebody standing at the trailhead with an old paper map is told, rather
   than the trail silently missing), `Proposed` is dropped because it is not
   ground, and blank/`Unknown` are dropped and counted - omit rather than
   guess. main() prints every dropped count; nothing is filtered silently.

3. THE ROUTE OWNER'S LINE WINS - features/NEARBY_TRAILS.md §5. A source that
   `owns_route_names` in the registry supplies that route's geometry, and
   another organization's copy of it is suppressed. See suppressed_by_owner()
   for why the match is on the source's own NAME field only and never on an
   alternate name.

CLOSED AREAS, WHICH ARE NOT A FILTER (#964)

NYS Parks closes GROUND, not trail segments: `oprhp_trail_closures` is four
polygons with the whole reason written as prose in a field called `Name`, and
no dates at all. The app's other two closure feeds cannot hold that - both land
in `client/src/lib/closureBanner.ts`'s `Closure`, which is a start and end mile
marker on the A.T. centerline and has no geometry, no trail id and no room for
a park. Measured 2026-08-24: two of the four closures do not touch the A.T. at
all, and the one that matters most - Hudson Highlands, closed until 2027 - is
entirely off it.

So the closure is DERIVED here instead, onto lines this export already ships:
apply_area_closures() intersects the polygons with the trail records and marks
what falls inside. The client needs no change for it, because the barred band
over this source already keys off `trail_status` (#950). See that function for
why a partly-covered trail is split at the boundary rather than closed whole.

WHAT THIS ARTIFACT SHIPS ON, AND THE ONE THING IT DOES NOT

It reaches hikers as of 2026-08-24, and the basis is worth reading before
changing anything here, because it was corrected once already.

OPRHP STATES TERMS. They permit reuse, REQUIRE attribution, and say
"informational and non-commercial purposes". They were recorded as *unstated*
for six days on the strength of a 200-character truncated read that stopped
exactly where the no-warranty disclaimer ends and the terms begin; the full
1,095 characters are quoted verbatim in sources.json's `oprhp_licence` so no
future reader has to re-fetch to check. The maintainer determined on
2026-08-24 that OurHike is a non-commercial use within them, with the
counter-reading recorded beside it.

NYNJTC, MOHONK PRESERVE AND NYS DEC STATE NOTHING - empty licenseInfo on the
AGOL items, and DEC is an on-prem service with no item to carry terms at all
and an empty copyrightText - so those four layers ship on the maintainer's
authorisation, the same footing atc_licence and photo_licence already use.
SOURCE_SURVEY.md §5's verdict on the full NYNJTC network is untouched by that:
still an agreement, not a scrape. DEC's own authorisation is #1019's scope
decision read as covering the data as well as its extent, which is argued in
sources.json's `dec_licence` along with the one-field way to undo it if that
reading is wrong.

THE ATTRIBUTION IS NOT OPTIONAL, and it is not this file's to render. OPRHP's
condition is met by client/src/map/credits.ts, which puts their name in the
map corner whenever their lines are drawn. If a future change ships these
lines somewhere that credit does not follow, the condition is broken - so the
export records each source's `steward` and `attribution` in its manifest, and
export_sources.py names them on the sources screen.

WHAT STILL DOES NOT SHIP: two of the four oprhp_* layers, and every DEC layer
but the trails. OPRHP's facilities (8,823 points) and park polygons (858) keep
`reaches_hikers: false` for a reason that is nothing to do with licensing -
nothing exports them. That is the field's other meaning (see
reaches_hikers_comment) and the two should not be blurred. The closures layer
left that group under #964 and now ships, derived onto the trail lines as
described above. DEC's back-country features (21,466 points), trailheads
(10,524) and lean-tos (314) are not registered at all - #1019 registered the
trail lines it needed and left the POIs to whoever answers
NYC_SOURCE_SURVEY.md §10(g)'s open question about whether any of them are
water, which is one of CLAUDE.md's four ways and raises the evidence bar.

The provenance line features/NEARBY_TRAILS.md §6 specifies - "Trail data: NYS
OPRHP", in a voice that does not outrun a steward who disclaims accuracy - is
NOT built here. It needs the sources screen to learn about held-back sources,
which is export_sources.py's `reaches_hikers` gate and #932's donate-line
question, not this artifact's. The manifest records each source's steward and
attribution so that screen has one place to read them from when it does.
"""

import json
from pathlib import Path

from shapely import wkt as shapely_wkt
from shapely.geometry import MultiLineString, shape
from shapely.ops import unary_union

from export_trails import geometry_to_wkt, simplify_records
from lib.blaze import NEUTRAL_FALLBACK, load_blaze_mapping, map_source_blaze
from lib.completeness import count_problems, fail_if_incomplete
from lib.feature_id import resolve_feature_id
from lib.hashing import sha256_file
from lib.source_registry import external_arcgis_sources, load_registry

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw" / "external"
OUT_DIR = ROOT / "data" / "processed"
SOURCES_PATH = ROOT / "sources.json"

ARTIFACT_NAME = "nearby_trails.geojson"
MANIFEST_NAME = "nearby_trails_manifest.json"

# Coordinates are written at six decimals - about 0.11 m of longitude at
# these latitudes - by export_trails.py's own precision rule: an order finer
# than the tolerance the geometry was simplified to, which is 1 m here (the
# `simplify_records` call in main()). OVERVIEW_COORDINATE_DECIMALS states the
# rule for its 100 m sketch and lands on four; 1 m lands on six.
#
# This was the one artifact writing coordinates with no precision floor at
# all: records_to_geojson serialises shapely's __geo_interface__, and the
# EPSG:5070 round trip inside simplify_records hands back full-precision
# doubles, ~17 significant digits each. The A.T.'s trails.geojson never had
# this problem because GDAL's GeoJSON driver caps it at seven decimals
# (export_trails.py's "why it is written here" block); this export writes its
# own JSON, so it caps its own. The digits dropped describe less ground than
# the simplification already discarded - and less than a tenth of the 1 m the
# simplification is allowed to move a vertex, so nothing downstream can tell
# the difference: build_trail_graph.py's ENDPOINT_SNAP_M is 8 m, and the
# off-route thresholds lib/dayHikeFollow.ts holds against derived geometry
# are 90 ft out / 45 ft back.
#
# What it buys, measured 2026-08-27 on the vertex bytes themselves (10,000
# uniform pairs in the artifact's own lon/lat range, JSON with the compact
# separators this export uses): 39.0 characters per full-precision pair
# against 22.8 at six decimals, 0.58x. The artifact is coordinates almost
# entirely, so the whole-file ratio should land near that; the run itself
# prints the byte count, which is where the measured after comes from.
NEARBY_COORDINATE_DECIMALS = 6

# What a `foot_field` has to read for a segment to be a hiking trail, where
# the source's entry does not say otherwise. OPRHP's domain also declares
# U/M/I/-99; none of the four appears in its live data (measured 2026-08-24,
# 16,641 rows: Y 16,441, N 200), and an unrecognised value is dropped and
# counted rather than assumed walkable.
#
# A source overrides this with `foot_allowed` in sources.json, next to the
# organization whose vocabulary it describes - DEC's `M` (MAINTAINED) is the
# case that made the default a default. Filter 1 above has the measurement.
FOOT_ALLOWED_DEFAULT = frozenset({"Y"})

# Raw status -> the `trail_status` the client reads, for the two that ship.
# Anything else is dropped by filter 2.
SHIPPED_STATUSES = {"Open": "open", "Closed": "closed"}

# What a source with no status column at all publishes. NYNJTC's two extracts,
# Mohonk's layer and DEC's have no status field: their rows are the trail as
# each organization maintains it, and inventing a "closed" for a layer that
# cannot say so would be the exact failure this pipeline's closure treatment
# exists to avoid.
DEFAULT_STATUS = "open"


def network_line_sources(registry: dict) -> list[dict]:
    """The external-organization entries that carry trail LINES.

    The same blaze-metadata marker export_trails.py's load_line_sources() uses,
    intersected with the external kind rather than subtracted from it - so one
    marker means "this is a trail-line source" across both exports, and `kind`
    alone decides which of the two picks it up. An external layer that is not
    lines (OPRHP's facilities points, its park polygons) carries no blaze keys
    and is skipped here without needing to be named.
    """
    return [s for s in external_arcgis_sources(registry) if "blaze_field" in s or "blaze_default" in s]


def shipped_line_source_keys(registry: dict) -> set[str]:
    """The network line sources whose geometry actually reaches hikers.

    WHO NEEDS THIS AND WHY (#1016). The water build measures against this
    export's artifact - `build_osm_water_reach.py` gates OSM springs on being
    near one of these lines, `fetch_trail_water.py` intersects streams with
    them - and the artifact holds every EXPORTED source, held back or not,
    because a reviewer has to be able to look at the map before a licence
    answer arrives. That is the right shape for this file and the wrong input
    for those two.

    A newly registered organization is review-only by default, which is the
    normal opening state rather than an edge case: `reaches_hikers` goes true
    when somebody answers about terms. Without this filter, registering one
    would immediately start deriving PUBLISHED water pins from lines nobody
    may publish - and drawing them over ground where the app shows no trail,
    because publish.py holds the whole artifact back when any source in it is
    held back.

    So the same field decides both, one file apart: `reaches_hikers` says
    whether an organization's data reaches a hiker, and water derived from
    that organization's trails is that organization's data reaching a hiker.
    """
    return {source["key"] for source in network_line_sources(registry) if source.get("reaches_hikers")}


def owned_route_names(registry: dict) -> dict[str, str]:
    """Route name -> the key of the source that owns that route's geometry.

    Read off `owns_route_names` in the registry, so the fact lives next to the
    organization making the claim: `centerline` owns "Appalachian Trail"
    because ATC does, `nynjtc_long_path` owns "Long Path" because NYNJTC does.
    A source never suppresses its own names.
    """
    owned: dict[str, str] = {}
    for entry in registry.get("sources", []):
        for name in entry.get("owns_route_names", []):
            owned[name] = entry["key"]
    return owned


def suppressed_by_owner(source_key: str, name, owned: dict[str, str]) -> bool:
    """Whether this feature is another organization's copy of a route somebody
    else owns - features/NEARBY_TRAILS.md §5's "the route owner's line always
    renders", applied.

    THE MATCH IS ON THE SOURCE'S OWN NAME FIELD AND ON NOTHING ELSE, and that
    restraint is the whole design. OPRHP's layer carries an `Alt_Name` too, and
    matching it would have been the obvious generalisation and would have
    deleted real trails: measured 2026-08-24, 26 segments read
    `Alt_Name: Appalachian Trail` while their own `Name` is something else -
    the 1777 East Trail (19), the Ramapo-Dunderberg (3), the Arden Surebridge,
    the Timp-Torne. Those are not copies of the A.T. They are distinct trails
    the A.T. runs along for a stretch, and an alternate name is how OPRHP says
    so. The Long Path has 23 more of the same shape.

    THE EVIDENCE THAT SUPPRESSION LOSES NOTHING, for the two routes owned
    today. The Long Path: all 124 OPRHP segments named "Long Path" lie within
    150 m of NYNJTC's own line, and NYNJTC's line extends further at both ends
    (measured 2026-08-24 - NYNJTC −74.61..−73.90 / 40.85..43.23 against
    OPRHP's −74.47..−73.90 / 40.99..42.47), so nothing is dropped that is not
    already drawn. The A.T.: #771 measured OPRHP's copy against ATC's at 1.8 m
    median agreement, diverging past 150 m on 14% of the in-park length and
    peaking at 1.24 km - which is the case FOR suppressing rather than against
    it, because that divergence is an old alignment and rendering it would put
    a second, wrong A.T. beside the real one.

    NOT GENERALISED TO PROXIMITY, though §5 describes the rule as
    "proximity + name". Name alone is what is implemented, because on the two
    routes owned today the two tests agree completely (the 150 m measurement
    above IS that check, run once here rather than per-feature at export time)
    and a proximity test needs the owner's geometry loaded, which this module
    deliberately does not do - ATC's centerline lives behind a different fetch.
    A source whose copy of a route is named differently enough to miss this
    test would draw twice, which is visible; that is the failure this accepts.
    """
    if name is None:
        return False
    owner = owned.get(str(name).strip())
    return owner is not None and owner != source_key


def resolve_blaze(source: dict, properties: dict, mapping: dict | None) -> tuple[str, str]:
    """One feature's (blaze_color, disposition).

    Four dispositions rather than lib/blaze.py's three, and the extra one is
    the reason this does not just call map_source_blaze directly:

      "default"  - the source declares a flat `blaze_default` and has no
                   per-feature field. nynjtc_highlands_trail's default is the
                   neutral "Unknown", which is that layer publishing no blaze
                   at all stated rather than a paint guessed at.
      "absent"   - the source HAS a blaze field and this row's value is null or
                   whitespace. Measured 2026-08-24, that is 2,038 of the 3,808
                   OPRHP rows this export keeps - 54%. Distinct from "unmapped"
                   and counted rather than warned about per feature: a value
                   nobody has reviewed is a gap in our table and deserves a
                   line each, while a source declining to state a blaze 2,038
                   times is one fact about the source, and printing it 2,038
                   times would bury the handful that are the other kind.
      "mapped" / "deferred" / "unmapped" - lib/blaze.py's, unchanged.

    NO CODED-DOMAIN DECODE, unlike export_trails.py's path. OPRHP's `Blaze` is
    domain-coded but its codes ARE the words ("Blue" -> "Blue", read off the
    live field metadata 2026-08-24), and NYNJTC's is a plain string with no
    domain at all, so the fetched value is already what the reviewed table is
    keyed on. If OPRHP ever renumbers to integer codes, every value becomes
    "unmapped" and says so loudly per feature - which is the right way for
    that change to be discovered.
    """
    field = source.get("blaze_field")
    if field is None:
        return source.get("blaze_default", NEUTRAL_FALLBACK), "default"

    raw = properties.get(field)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return NEUTRAL_FALLBACK, "absent"
    return map_source_blaze(raw, mapping)


def keep_reason(source: dict, properties: dict, geometry, owned: dict[str, str]) -> str | None:
    """None if this feature ships, else the reason it does not - a short string
    main() counts and prints. Every drop is one of these; there is no path out
    of this function that discards a feature without naming why.

    NOTHING IN HERE ASKS WHERE THE FEATURE IS, since #1019. Two tests used to:
    a bounding box around New York City and an exclusion of OPRHP's `Long
    Island` region. Both are gone by the maintainer's decision of 2026-08-25
    (quoted in this module's docstring), and the geometry argument survives
    only as the emptiness check - a source that hands us nothing to draw."""
    if geometry is None or geometry.is_empty:
        return "no geometry"

    foot_field = source.get("foot_field")
    if foot_field and properties.get(foot_field) not in source.get("foot_allowed", FOOT_ALLOWED_DEFAULT):
        return f"not a foot trail: {foot_field}={properties.get(foot_field)!r}"

    status_field = source.get("status_field")
    if status_field and properties.get(status_field) not in SHIPPED_STATUSES:
        return f"status not shipped: {properties.get(status_field)!r}"

    name_field = source.get("name_field", "Name")
    if suppressed_by_owner(source["key"], properties.get(name_field), owned):
        return f"route owned by {owned[str(properties.get(name_field)).strip()]}"

    return None


def build_records(source: dict, features: list[dict], owned: dict[str, str]) -> tuple[list[dict], dict]:
    """One source's shippable features as export_trails.py-shaped records
    (id/source/name/blaze_color/trail_status/wkt), plus a stats dict of what
    was dropped and why."""
    key = source["key"]
    mapping = load_blaze_mapping().get(key)
    name_field = source.get("name_field", "Name")
    status_field = source.get("status_field")

    records: list[dict] = []
    drops: dict[str, int] = {}
    blazes: dict[str, int] = {}

    for index, feature in enumerate(features):
        properties = feature.get("properties") or {}
        raw_geometry = feature.get("geometry")
        geometry = shape(raw_geometry) if raw_geometry else None

        reason = keep_reason(source, properties, geometry, owned)
        if reason is not None:
            drops[reason] = drops.get(reason, 0) + 1
            continue

        wkt = geometry_to_wkt(raw_geometry)
        feature_id = resolve_feature_id(key, feature, properties, index)
        if wkt is None:
            # export_trails.py's convention, verbatim: loud, named, and not a
            # silent skip. A geometry shapely could read but geometry_to_wkt
            # cannot is a shape this export has never seen.
            print(
                f"WARNING: {key} feature {feature_id!r} has unsupported geometry ({(raw_geometry or {}).get('type')!r}) - skipped"
            )
            drops["unsupported geometry"] = drops.get("unsupported geometry", 0) + 1
            continue

        blaze_color, disposition = resolve_blaze(source, properties, mapping)
        blazes[disposition] = blazes.get(disposition, 0) + 1
        if disposition == "unmapped":
            # The loud one WIREFRAMES.md §3 requires - a colour the map has
            # never heard of must never invent a paint and must never pass
            # quietly. "deferred" is a decision already recorded in
            # reference/blaze_mapping.json and "absent" is the source saying
            # nothing, so neither is repeated per feature.
            print(
                f"WARNING: {key} feature {feature_id!r} has an unreviewed blaze "
                f"({properties.get(source.get('blaze_field'))!r}) - drawing {blaze_color!r}. "
                f"Add a row to reference/blaze_mapping.json."
            )

        raw_status = properties.get(status_field) if status_field else None
        trail_status = SHIPPED_STATUSES.get(raw_status, DEFAULT_STATUS)
        records.append(
            {
                "id": f"{key}:{feature_id}",
                "source": key,
                "name": properties.get(name_field),
                "blaze_color": blaze_color,
                "trail_status": trail_status,
                # WHICH KIND OF CLOSED, stated rather than inferred from the
                # absence of the other kind (#964). This one is the steward's
                # own long-term status column - OPRHP marks a trail `Closed`
                # and means it is not coming back soon - as against the
                # temporary closed AREAS apply_area_closures() derives.
                # features/NEARBY_TRAILS.md §3 needs the sheet to say
                # different things about the two, and "no closure_kind means
                # long-term" would make that a rule a reader has to know
                # rather than a fact the data carries.
                **({"closure_kind": "long_term"} if trail_status == "closed" else {}),
                "wkt": wkt,
            }
        )

    return records, {"kept": len(records), "dropped": drops, "blazes": blazes}


def closure_area_sources(registry: dict) -> list[dict]:
    """The registered layers that publish CLOSED AREAS rather than trail lines
    (#964). NYS Parks' temporary closures is the first and only one today."""
    return [s for s in external_arcgis_sources(registry) if s.get("closure_areas")]


def load_closure_areas(sources: list[dict]) -> list[dict]:
    """Every closed area on the ground right now, as {geometry, reason, place,
    source}.

    AN ABSENT OR EMPTY LAYER IS NOT AN ERROR, and this is the one place in this
    module where zero is a legitimate answer rather than a broken fetch.
    `oprhp_trail_closures` carries `may_be_empty: true` in the registry for
    exactly this: a week with nothing closed is a good week in the parks, and a
    gate that read it as failure would make the honest state indistinguishable
    from a broken one.
    """
    areas: list[dict] = []
    for source in sources:
        raw_path = RAW_DIR / f"{source['key']}.geojson"
        if not raw_path.exists():
            print(f"  {source['key']}: not fetched - no area closures applied")
            continue
        features = json.loads(raw_path.read_text(encoding="utf-8")).get("features", [])
        reason_field = source.get("reason_field")
        place_field = source.get("place_field")
        for feature in features:
            raw_geometry = feature.get("geometry")
            if not raw_geometry:
                continue
            geometry = shape(raw_geometry)
            if geometry.is_empty:
                continue
            properties = feature.get("properties") or {}
            areas.append(
                {
                    "geometry": geometry,
                    "reason": (properties.get(reason_field) or "").strip() or None,
                    "place": (properties.get(place_field) or "").strip() or None,
                    "source": source["key"],
                }
            )
    return areas


def _line_parts(geometry) -> list:
    """A geometry's drawable LineStrings, and nothing else.

    `difference` and `intersection` on a line and a polygon can return a
    GeometryCollection carrying stray Points where the line only grazes the
    boundary. A Point is not a trail, and export_trails.py's simplify guard
    already records what a zero-length line does to a map, so both are dropped
    here rather than written out as geometry nobody can walk.
    """
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry] if len(set(geometry.coords)) >= 2 else []
    if geometry.geom_type in ("MultiLineString", "GeometryCollection"):
        return [part for piece in geometry.geoms for part in _line_parts(piece)]
    return []


def _merge(parts: list) -> str:
    """One WKT for a list of LineStrings, kept multi-part rather than merged
    into a single line: a closure can cut a trail into pieces that do not join,
    and merging would draw a line across the gap between them."""
    if len(parts) == 1:
        return parts[0].wkt
    return MultiLineString(parts).wkt


def apply_area_closures(records: list[dict], areas: list[dict]) -> tuple[list[dict], dict]:
    """Split every trail record against the closed areas, so the part inside a
    closure ships closed and the part outside ships open (#964).

    WHY SPLIT RATHER THAN CLOSE THE WHOLE FEATURE, which was the obvious
    cheaper thing and is wrong. Measured 2026-08-24 against the live layers, 99
    exported features touch a closed area: 66 lie wholly inside, and 33 only
    partly. Closing those 33 whole would draw the barred band along the entire
    Ramapo-Dunderberg on the strength of 16.7% of its length, and along the
    whole Suffern-Bear Mountain on 0.0% - a trail that touches the boundary and
    goes nowhere near the closure. A band across a trail that is open is the
    cry-wolf failure wrongWay.test.ts names for its own module, on a mark a
    hiker is meant to obey without checking.

    THE DIRECTION THIS ERRS, stated because the split makes it a choice rather
    than an accident: a line is closed where it is INSIDE the polygon, by
    `intersection`. Geometry the polygon merely touches is not inside it, so a
    grazing trail stays open. The opposite reading - closing anything that
    intersects at all - is what produces the Suffern-Bear Mountain case.

    WHAT IT DOES NOT DO: invent a date. OPRHP publishes none per feature
    ("Closed Until 2027" is prose inside the reason, not a field), so a closed
    record carries the reason verbatim and nothing this module made up.
    """
    if not areas:
        return records, {"areas": 0, "closed": 0, "split": 0, "wholly_closed": 0}

    closed_union = unary_union([a["geometry"] for a in areas])

    out: list[dict] = []
    stats = {"areas": len(areas), "closed": 0, "split": 0, "wholly_closed": 0}

    for record in records:
        geometry = shapely_wkt.loads(record["wkt"])
        if not geometry.intersects(closed_union):
            out.append(record)
            continue

        inside = _line_parts(geometry.intersection(closed_union))
        outside = _line_parts(geometry.difference(closed_union))

        if not inside:
            # Touching the boundary and no more. Not inside anything.
            out.append(record)
            continue

        # The area whose reason this record should carry: the one it overlaps
        # most, so a trail crossing two closures is described by the one it
        # spends most of its closed length in rather than by whichever happened
        # to come first in the file.
        best = max(areas, key=lambda a: geometry.intersection(a["geometry"]).length)

        out.append(
            {
                **record,
                "id": f"{record['id']}:closed" if outside else record["id"],
                "trail_status": "closed",
                # features/NEARBY_TRAILS.md §3 needs the sheet to tell a
                # long-term closed trail from a temporarily closed area, and
                # `trail_status` alone cannot: both are "closed". This is that
                # second signal.
                "closure_kind": "area",
                "closure_reason": best["reason"],
                "closure_source": best["source"],
                "wkt": _merge(inside),
            }
        )
        stats["closed"] += 1

        if outside:
            out.append({**record, "id": f"{record['id']}:open", "wkt": _merge(outside)})
            stats["split"] += 1
        else:
            stats["wholly_closed"] += 1

    return out, stats


def _drawable_after_cut(geom_type: str, coords) -> bool:
    """Whether every line part still has two distinct vertices - the same
    question export_trails' _has_drawable_geometry asks, re-asked here
    because the answer can CHANGE at six decimals: two vertices less than
    the rounding step apart land on the same grid point, and a zero-length
    LineString draws as nothing while the run reports success."""
    lines = coords if geom_type == "MultiLineString" else [coords]
    return all(len({tuple(pair) for pair in line}) >= 2 for line in lines)


def _rounded_geometry(geometry) -> dict:
    """`__geo_interface__` with every coordinate cut to
    NEARBY_COORDINATE_DECIMALS - see that constant for the derivation. A cut,
    not a re-derivation: the vertices are the simplified ones, minus digits
    finer than the simplification's own tolerance.

    With one exception, and it is simplify_records' own never-drop
    convention: a feature the cut would degenerate - a closure sliver or a
    source line shorter than ~0.1 m in both axes, whose two vertices round
    onto one grid point - keeps its full-precision vertices instead. A few
    dozen uncut characters against a trail marked closed by an invisible
    zero-length line."""
    geo = geometry.__geo_interface__

    def walk(coords, cut: bool):
        if len(coords) == 0:
            return []
        if isinstance(coords[0], (int, float)):
            if cut:
                return [round(value, NEARBY_COORDINATE_DECIMALS) for value in coords]
            return list(coords)
        return [walk(part, cut) for part in coords]

    # Only the two line types reach here (build_records skips anything else,
    # and the closure split merges back to them); a type this predicate does
    # not understand is passed through uncut rather than guessed at.
    if geo["type"] not in ("LineString", "MultiLineString"):
        return {"type": geo["type"], "coordinates": walk(geo["coordinates"], cut=False)}

    rounded = walk(geo["coordinates"], cut=True)
    if _drawable_after_cut(geo["type"], rounded):
        return {"type": geo["type"], "coordinates": rounded}
    return {"type": geo["type"], "coordinates": walk(geo["coordinates"], cut=False)}


def records_to_geojson(records: list[dict]) -> dict:
    """The FeatureCollection the client draws. Properties only - no geometry
    re-derivation - so what is written is what was clipped and simplified,
    at the precision NEARBY_COORDINATE_DECIMALS caps."""
    from shapely import wkt as shapely_wkt

    features = []
    for record in records:
        geometry = shapely_wkt.loads(record["wkt"])
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": record["id"],
                    "source": record["source"],
                    "name": record["name"],
                    "blaze_color": record["blaze_color"],
                    "trail_status": record["trail_status"],
                    # Only on a closed record, and only when the steward said
                    # something. Omitted rather than null everywhere else -
                    # 3,663 features do not need two empty keys each, and an
                    # absent key reads as "no reason given" the same way an
                    # absent capacity does on a shelter.
                    **({"closure_kind": record["closure_kind"]} if record.get("closure_kind") else {}),
                    **({"closure_reason": record["closure_reason"]} if record.get("closure_reason") else {}),
                },
                "geometry": _rounded_geometry(geometry),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def exported_bbox(records: list[dict]) -> list[float] | None:
    """The ground this artifact actually covers, as [west, south, east, north].

    REPLACES A DECLARED EXTENT WITH A MEASURED ONE (#1019). The manifest used
    to carry `ring_bbox` - the box this module clipped to - which answered
    "what did we decide to cover" and was read by nobody. Now that nothing is
    clipped there is no such decision to report, and the honest neighbouring
    fact is what the exported lines actually span. Derived from the records
    rather than declared above them, so it cannot go stale when a source is
    added or an organization's layer grows.

    None when there are no records, which the completeness gate has already
    refused to let happen for a real run; a caller reading this key still has
    to handle it rather than index into an empty list.
    """
    if not records:
        return None
    bounds = [shapely_wkt.loads(record["wkt"]).bounds for record in records]
    return [
        min(b[0] for b in bounds),
        min(b[1] for b in bounds),
        max(b[2] for b in bounds),
        max(b[3] for b in bounds),
    ]


def write_artifact(records: list[dict], per_source: dict) -> dict:
    """Write the artifact and return its manifest entry."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / ARTIFACT_NAME
    path.write_text(json.dumps(records_to_geojson(records), separators=(",", ":")))

    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "feature_count": len(records),
        "bbox": exported_bbox(records),
        "sources": per_source,
    }


def main() -> dict:
    registry = load_registry(SOURCES_PATH)
    sources = network_line_sources(registry)
    owned = owned_route_names(registry)
    print(f"Route names owned by their steward: {owned}")

    all_records: list[dict] = []
    counts: dict[str, int] = {}
    per_source: dict[str, dict] = {}

    for source in sources:
        key = source["key"]
        raw_path = RAW_DIR / f"{key}.geojson"
        if not raw_path.exists():
            raise FileNotFoundError(
                f"{raw_path} is missing - run fetch_external_layers.py first. "
                f"({key} is registered as an external layer, so it is not part of fetch_all.py's A.T. fetch.)"
            )
        features = json.loads(raw_path.read_text(encoding="utf-8")).get("features", [])
        records, stats = build_records(source, features, owned)

        print(f"  {key}: {stats['kept']} of {len(features)} features kept")
        for reason, count in sorted(stats["dropped"].items(), key=lambda kv: -kv[1]):
            print(f"      dropped {count:>6,}  {reason}")
        for disposition, count in sorted(stats["blazes"].items(), key=lambda kv: -kv[1]):
            print(f"      blaze   {count:>6,}  {disposition}")

        counts[key] = stats["kept"]
        per_source[key] = {
            "steward": source.get("steward"),
            "attribution": source.get("attribution"),
            "reaches_hikers": source.get("reaches_hikers"),
            **stats,
        }
        all_records.extend(records)

    # export_trails.py's completeness gate, for the same reason it has one: a
    # source that silently returns zero features - an ArcGIS schema change, a
    # renamed status value - must fail the run rather than quietly shrink the
    # map. Runs before anything is written.
    fail_if_incomplete(count_problems(counts), label="Incomplete nearby-trails export")

    # The closed areas (#964), applied AFTER the completeness gate and BEFORE
    # the simplification. After, because a closure splitting one feature into
    # two must not be able to satisfy a gate that is counting whether a source
    # produced anything. Before, because simplify_records guarantees the
    # tolerance against the geometry it is handed, and the split is what makes
    # that geometry final.
    areas = load_closure_areas(closure_area_sources(registry))
    all_records, closure_stats = apply_area_closures(all_records, areas)
    if closure_stats["areas"]:
        print(
            f"  {closure_stats['areas']} closed area(s): "
            f"{closure_stats['closed']} trail sections closed "
            f"({closure_stats['wholly_closed']} wholly, {closure_stats['split']} split at the boundary)"
        )
    else:
        print("  no closed areas on the ground - nothing marked closed")

    # Simplified with export_trails.py's own function at its own 1 m tolerance,
    # imported rather than reimplemented: it carries a documented guarantee
    # (Douglas-Peucker, endpoints preserved, and a degenerate result falls back
    # to the original geometry rather than being dropped) that a second copy
    # would be one edit away from losing.
    simplified = simplify_records(all_records)
    manifest = write_artifact(simplified, per_source)
    manifest["closures"] = closure_stats

    size = Path(manifest["path"]).stat().st_size
    print(f"\n  {manifest['feature_count']:,} features -> {manifest['path']} ({size:,} bytes)")

    held_back = [k for k, s in per_source.items() if not s["reaches_hikers"]]
    if held_back:
        print(
            f"  HELD BACK: {', '.join(held_back)} carry reaches_hikers: false, so publish.py "
            f"will not upload this artifact. See sources.json's licence blocks."
        )

    manifest_path = OUT_DIR / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"  manifest -> {manifest_path}")
    return manifest


if __name__ == "__main__":
    main()
