"""Export the trail lines OTHER organizations maintain, for the map to draw
behind the chosen trail (#950, features/NEARBY_TRAILS.md).

export_trails.py's subject is the A.T.: two ATC sources, clipped to a 30-mile
corridor around ATC's own centerline. This module's subject is everything else
already on the ground a hiker is standing on - NYS OPRHP's statewide layer and
NYNJTC's two public extracts today, DEC's Catskills and the NJ layers when
pipeline/NYC_SOURCE_SURVEY.md's next verdicts are acted on. Different sources,
a different extent, and a different licence footing, which is why it is a
second export rather than a branch inside the first.

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

THE FOUR FILTERS, AND THE EVIDENCE UNDER EACH

All counts below were measured on 2026-08-24 against the layers
fetch_external_layers.py had just fetched, re-running the census
spike_nyc_trails.py first ran on 2026-08-18. Where the two disagree the newer
number is the one written down, and none of them disagreed by more than the
statewide/ring difference the ring clip explains.

1. HIKING ONLY - the maintainer's decision, 2026-08-18 ("Only keep hiking
   trails for now... It's OurHike, not OurBike"). A source declaring a
   `foot_field` keeps only rows that allow foot travel; a source with no use
   flags at all keeps every row, because NYNJTC publishes hiking trails and
   nothing else. Statewide, OPRHP's Foot column is a clean two-value domain
   (Y 16,441 / N 200).

2. THE RING - NYC_SOURCE_SURVEY.md §1's proposal, applied. A feature is kept
   if any part of it INTERSECTS the ring; its geometry is never cut at the
   boundary. That mirrors export_trails.py's own corridor clip, and the reason
   is the same one stated there: cutting would end a trail at a line nobody
   drew on the ground. So a kept feature may run some distance past the ring
   - the Long Path sections that straddle 42.55° are exported whole.

   BE CLEAR ABOUT WHAT THAT DOES NOT DO: it saves the geometry of features
   that cross the edge, not features that lie wholly beyond it. Measured
   2026-08-24, 10 of NYNJTC's 43 Long Path sections are north of the ring
   entirely and are dropped, so the exported Long Path does stop - just at a
   section boundary rather than mid-line. See RING_BBOX (b), which is where
   that is argued.

3. STATUS - the maintainer's decision, 2026-08-18, taken with the statewide
   counts in front of them: `Open` ships, `Closed` SHIPS DRAWN AS CLOSED (so
   somebody standing at the trailhead with an old paper map is told, rather
   than the trail silently missing), `Proposed` is dropped because it is not
   ground, and blank/`Unknown` are dropped and counted - omit rather than
   guess. main() prints every dropped count; nothing is filtered silently.

4. THE ROUTE OWNER'S LINE WINS - features/NEARBY_TRAILS.md §5. A source that
   `owns_route_names` in the registry supplies that route's geometry, and
   another organization's copy of it is suppressed. See suppressed_by_owner()
   for why the match is on the source's own NAME field only and never on an
   alternate name.

WHAT THIS ARTIFACT MAY NOT DO YET

Nothing here reaches a hiker. Every source it reads carries
`reaches_hikers: false`, because neither OPRHP nor NYNJTC has stated terms -
sources.json's `oprhp_licence` and `nynjtc_licence` blocks record both asks as
open. So this export writes its file unconditionally and publish.py refuses to
upload it while any source in it is held back. The gate is in the publish step
rather than here on purpose: the day a licence answer lands, flipping one
registry field is the whole change, and nobody has to remember that a second
script also needs editing.

Writing unconditionally is what lets the map be REVIEWED before anybody
decides whether it may ship, and that needs one more thing to be true than it
sounds: since #197 the client refuses to draw an artifact it cannot check
against a published hash, and publish.py writes that manifest into the bucket
rather than into data/processed/. So serve_processed.py synthesizes one from
the files on disk - without it, the map this export exists to produce is the
one map nobody can look at.

The provenance line features/NEARBY_TRAILS.md §6 specifies - "Trail data: NYS
OPRHP", in a voice that does not outrun a steward who disclaims accuracy - is
NOT built here. It needs the sources screen to learn about held-back sources,
which is export_sources.py's `reaches_hikers` gate and #932's donate-line
question, not this artifact's. The manifest records each source's steward and
attribution so that screen has one place to read them from when it does.
"""

import json
from pathlib import Path

from shapely.geometry import box, shape

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

# NYC_SOURCE_SURVEY.md §1's "as a spike bbox" - Delaware Water Gap to the
# Connecticut line, New York Harbor to the Catskills' northern escarpment.
#
# `@unvalidated` - a survey's PROPOSAL, not a decision anybody has taken. §1
# says so in its own words: the ring is "proposed, with edges", and two of
# those edges are explicitly the maintainer's rather than the survey's. Both
# are still open, and both move this number:
#
#   (a) LONG ISLAND. The survey's county list does not include Nassau or
#       Suffolk - "NYNJTC does not cover LI and the scope call did not name
#       it" - but the bbox above reaches to −73.4° and takes in the western
#       half of the island anyway. Measured 2026-08-24, and the two numbers
#       are worth keeping apart because keep_reason() tests the unit BEFORE
#       the foot and status filters: main() reports 2,058 segments dropped as
#       Long Island, of which 1,951 would have passed every other filter too.
#       That 1,951 against the 5,759 that otherwise survive is the number the
#       decision turns on - a bbox-only ring would be 34% ground the scope
#       call never asked for. EXCLUDED_UNITS below resolves that toward the
#       county list, which is the closest thing to a decision that exists;
#       main() prints what it drops so the other answer is one constant away.
#   (b) THE NORTHERN CUT. The Long Path continues past the Catskills toward
#       Albany, reaching 43.23°, and this box cuts it: measured 2026-08-24,
#       10 of NYNJTC's 43 sections lie entirely north of 42.55° and are
#       dropped. Keeping whole features rather than cutting geometry (filter
#       2) does NOT save them - it only means the 33 that survive are not
#       themselves truncated. §1(b) guesses this is the right call for v1
#       ("cut the trail at the ring's edge AND SAY SO ON SCREEN rather than
#       pretend it ends there"), and the second half of that sentence is not
#       built: nothing on the map tells a hiker at Windham that the Long Path
#       continues past where our line stops. **#557 — Draw the map from
#       several coverage units, and say plainly where they end** is that
#       work's home, and until it lands this export produces a trail with a
#       silent end, which is the honest description of it.
#
# What would settle it: the maintainer answering §1's two NEEDS REVIEW edges,
# on #768. Until then this is a proposal being applied, and saying so is the
# point of the tag.
RING_BBOX = (-75.4, 40.45, -73.4, 42.55)

# See RING_BBOX (a). Expressed in OPRHP's own vocabulary - its `Unit` column
# is its eleven administrative regions - because that is the one place the
# distinction is already drawn by the steward rather than inferred by us.
EXCLUDED_UNITS = frozenset({"Long Island"})

# What a `foot_field` has to read for a segment to be a hiking trail. OPRHP's
# domain also declares U/M/I/-99; none of the four appears in the live data
# (measured 2026-08-24, 16,641 rows: Y 16,441, N 200), and an unrecognised
# value is dropped and counted rather than assumed walkable.
FOOT_ALLOWED = frozenset({"Y"})

# Raw status -> the `trail_status` the client reads, for the two that ship.
# Anything else is dropped by filter 3.
SHIPPED_STATUSES = {"Open": "open", "Closed": "closed"}

# What a source with no status column at all publishes. NYNJTC's two extracts
# have no status field: their sections are the trail as NYNJTC maintains it,
# and inventing a "closed" for a layer that cannot say so would be the exact
# failure this pipeline's closure treatment exists to avoid.
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
    of this function that discards a feature without naming why."""
    if geometry is None or geometry.is_empty:
        return "no geometry"

    if not box(*RING_BBOX).intersects(geometry):
        return "outside the ring"

    unit_field = source.get("unit_field")
    if unit_field and properties.get(unit_field) in EXCLUDED_UNITS:
        return f"excluded unit: {properties.get(unit_field)}"

    foot_field = source.get("foot_field")
    if foot_field and properties.get(foot_field) not in FOOT_ALLOWED:
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
        records.append(
            {
                "id": f"{key}:{feature_id}",
                "source": key,
                "name": properties.get(name_field),
                "blaze_color": blaze_color,
                "trail_status": SHIPPED_STATUSES.get(raw_status, DEFAULT_STATUS),
                "wkt": wkt,
            }
        )

    return records, {"kept": len(records), "dropped": drops, "blazes": blazes}


def records_to_geojson(records: list[dict]) -> dict:
    """The FeatureCollection the client draws. Properties only - no geometry
    re-derivation - so what is written is what was clipped and simplified."""
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
                },
                "geometry": json.loads(json.dumps(geometry.__geo_interface__)),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_artifact(records: list[dict], per_source: dict) -> dict:
    """Write the artifact and return its manifest entry."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / ARTIFACT_NAME
    path.write_text(json.dumps(records_to_geojson(records), separators=(",", ":")))

    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "feature_count": len(records),
        "ring_bbox": list(RING_BBOX),
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

    # Simplified with export_trails.py's own function at its own 1 m tolerance,
    # imported rather than reimplemented: it carries a documented guarantee
    # (Douglas-Peucker, endpoints preserved, and a degenerate result falls back
    # to the original geometry rather than being dropped) that a second copy
    # would be one edit away from losing.
    simplified = simplify_records(all_records)
    manifest = write_artifact(simplified, per_source)

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
