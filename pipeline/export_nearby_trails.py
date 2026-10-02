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
  `closure_kind` / `closure_reason` / `closure_source`
                  on closed records only: which kind of closed, the closing
                  org's own words, and the closure LAYER's registry key -
                  what lets lib/lineDetail.ts speak a temporary area closure
                  in the closing organization's voice rather than the
                  line-drawing organization's (#1142).

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

SHARED GROUND, WHICH RIDES IN THE TILES AND NOWHERE ELSE (#1384)

Where two trails run on one treadway - the Ramapo-Dunderberg on the A.T. for
a mile, the Long Path on the Arden-Surebridge - both sources draw their own
line on the same pixels and the last painted wins. lib/concurrency.py finds
those stretches (trail against trail, 10 m and 50 m, both measured there)
and writes each as a PAIR of features on one chord: the same coordinates,
each trail's own properties, `concurrent_with` naming the other,
`concurrent_source` its source key and `concurrent_side` +1 or -1, so the
client can offset each half to its own side of the line and weigh the
stretch at the heavier of the two tiers.

The pool is this export's records plus ATC's CENTERLINE, loaded from the
A.T. fetch's own raw file through export_trails.py's own functions
(load_at_centerline) - the raw file because the A.T. export runs later in
the workflow than this one, held there by the identity gate
(.github/tests/test_identity_ledger_regeneration.py), and a run reads what
this run fetched, never a cache. Simplified to the same 1 m the published
line is, so the pair sits on the line the map draws to within a metre.
ATC's side trails are deliberately NOT in the pool: lib/concurrency.py's
docstring carries the measurement (they share no ground with the centerline
at 5 m or under) and the reason (they carry other organizations' trails
under ATC's names). When the A.T. fetch is not there - a checkout with only
the external layers - the pairing runs over the network alone and main()
prints a HELD BACK line, the same shape as trail_miles.json's.

The pairs go into concurrent_trails.geojson beside the lines and then INTO
THE VECTOR TILES, unioned with the lines when write_tiles cuts them. They
do NOT go into nearby_trails.geojson: eleven other scripts read that file
as the network's topology (build_trail_graph.py routes over it,
fetch_trail_water.py measures water against it), and a stretch of ground
appearing twice more would be a duplicate edge to every one of them. The
tiles are what the map draws and the only reader that wants the pairs, and
cut_cells.py carries them into the coverage cells for free. The overview
sketch takes the plain records, as before.

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
import math
import resource
import time
from pathlib import Path

import duckdb
import numpy as np
import shapely
from pmtiles.reader import MmapSource, Reader
from shapely import wkt as shapely_wkt
from shapely.geometry import MultiLineString, shape
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union

from export_trails import (
    _TO_METRIC,
    OVERVIEW_SIMPLIFY_TOLERANCE_M,
    _flat_lines,
    _overview_coordinates_all,
    build_trail_records,
    geometry_to_wkt,
    load_features,
    load_line_sources,
    normalize_source_features,
    simplify_records,
)
from lib.batch_geometry import from_wkt_all, reproject, round_like_python
from lib.blaze import NEUTRAL_FALLBACK, load_blaze_mapping, map_source_blaze
from lib.completeness import count_problems, fail_if_incomplete
from lib.concurrency import AT_CENTERLINE_SOURCE, find_shared_ground
from lib.duplicates import apply_duplicates, find_duplicates
from lib.feature_id import resolve_feature_id
from lib.hashing import sha256_file
from lib.manifest_paths import to_manifest_path
from lib.source_registry import external_sources, load_registry

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw" / "external"
OUT_DIR = ROOT / "data" / "processed"
SOURCES_PATH = ROOT / "sources.json"

ARTIFACT_NAME = "nearby_trails.geojson"
MANIFEST_NAME = "nearby_trails_manifest.json"

# The A.T. fetch's raw directory and registry - export_trails.py's RAW_DIR and
# SOURCES_PATH, named here so a test can point this module's reading of the
# centerline somewhere else without reaching into that module (#1384, the
# SHARED GROUND block above).
AT_RAW_DIR = ROOT / "data" / "raw"
AT_SOURCES_PATH = SOURCES_PATH

# The shared-ground pairs (#1384): written beside the lines, unioned into the
# tiles, never into ARTIFACT_NAME - the header says why.
CONCURRENT_ARTIFACT_NAME = "concurrent_trails.geojson"

# The corridor-view sketch of this whole network - export_trails.py's
# write_overview pattern (#869) applied to the artifact above, so the opening
# camera can draw every organization's trails without fetching or parsing the
# full file (#1135). Its own flat name for publish.py and lib/config.ts to
# agree on, like NEARBY_TRAILS_KEY.
OVERVIEW_ARTIFACT_NAME = "network_overview.geojson"

# THE SAME LINES AS VECTOR TILES (#1257), which is how the map draws them
# above the seam since the GeoJSON above outgrew a phone.
#
# On 2026-09-07 the artifact reached 228,820,578 bytes - nationwide USFS
# trails, #1231 - and every phone that fetched it whole crashed its map
# (#1254): the file was parsed entire on the way to MapLibre, and a renderer
# at 1.7 GB is a dead one. A PMTiles archive is read by byte range - the
# header, one directory, then only the tiles under the viewport - so what a
# phone holds is a few kilobytes per tile whatever the archive weighs. The
# basemap has shipped that way all along; these lines never did.
#
# GDAL writes it, through the same DuckDB spatial extension every exporter
# here already loads - no new tool. Measured against that day's real file on
# a 4-core runner: 112,378 features tiled z9-z14 in 92 s into 132,995,363
# bytes and 173,209 tiles, layer `trails`, every property intact - and 388
# bytes of header and root directory to open, which is what a phone reads
# before its first tile.
#
# THE ZOOM RANGE IS A CONTRACT WITH THE CLIENT. client/src/lib/config.ts
# declares NEARBY_TRAILS_TILES_MIN_ZOOM and _MAX_ZOOM for the source it
# builds over these tiles, and tests/test_export_nearby_trails.py reads that
# file to hold the two ends equal - a tileset the map asks the wrong zooms of
# draws nothing, silently.
#
# THE FLOOR WAS 9 AND IS 5 (#1613). 9 was the pin seam, where the full
# network's layers start, "below it the overview sketch above still draws" -
# and that sketch is the point. `network_overview.geojson` is 12,238,110 bytes
# in release 2026-09-16-4, handed whole to MapLibre's one worker on every
# launch and cut into tiles there; it costs the A.T.'s own line 2,470 ms of
# that worker's queue, measured 2026-09-21 (features/LAUNCH_BUDGET.md §7).
# The archive could not take the sketch's place below z9 because these zooms
# were never cut, and they were never cut because the sketch drew there.
#
# 5 breaks that circle. It is the floor §7.1's experiment cut the A.T.'s own
# line at, and it carries the continental view a laptop opens on. @unvalidated
# against the widest camera a hiker actually reaches, which nothing records.
#
# WHAT IT COSTS THE ARCHIVE, measured on the first cut rather than predicted.
# UA release 2026-09-23-2, the run that made this floor real:
#
#   nearby_trails.pmtiles          155,229,297 -> 181,668,171   (+26.4 MB)
#   nearby_trails_context.pmtiles  did not exist -> 22,176,121
#
# THE PREDICTION HERE WAS WRONG AND IS WORTH LEAVING VISIBLE. It read: "four
# zooms of a nationwide network, each about a quarter of the one below it: z9
# alone is 9.65 MB, so z5-z8 together are a few megabytes." That reasoning
# runs the pyramid the wrong way. A coarse tile covers more ground and
# therefore carries more of the network's geometry, so z5-z8 are each LARGER
# than z9, not smaller - 22.2 MB against 9.65 MB, about nine times the "few
# megabytes" guessed at.
#
# It does not change the decision, and that is the point of saying so rather
# than quietly editing the figure: these tiles are read by BYTE RANGE, so a
# phone pays for the tiles its viewport touches and never for the file. 22 MB
# sitting in a bucket is not 22 MB on anybody's launch. That is #1257's whole
# argument, applied one seam lower - and it is the argument that has to carry
# the weight now that the size does not.
#
# 14 is where the Fine hiking sheet stops and MapLibre overzooms.
TILES_ARTIFACT_NAME = "nearby_trails.pmtiles"
TILES_LAYER = "trails"
TILES_MIN_ZOOM = 5
TILES_MAX_ZOOM = 14


def _metres_per_pixel(zoom: float, latitude: float = 40.0) -> float:
    """Ground distance one CSS pixel covers at `zoom`, MapLibre's 512 px tiles.

    40 degrees north because that is roughly where the network's mass is - the
    Appalachians and the Sierra - and Mercator's scale factor is a cosine, so
    one number cannot be right everywhere. It is optimistic in Maine and
    pessimistic in Georgia, by about 15% either way across the shipped extent.
    """
    return 156543.03392 * math.cos(math.radians(latitude)) / (2**zoom) / 2


# WHERE THE SKETCH HANDS THE NETWORK OVER, and therefore what it has to be
# good enough for (#1775). The sketch used to draw to CORRIDOR_MAX_ZOOM = 9
# and was cut at export_trails.py's OVERVIEW_SIMPLIFY_TOLERANCE_M = 100 m,
# which is about one pixel there. Since #1615 cut the tiles from z5 the tiles
# can take z5-z9, so the sketch only still owns z0-z5 - where 100 m is 16
# times finer than a pixel and the file is paying for every one of those
# digits on every launch.
OVERVIEW_SEAM_ZOOM = TILES_MIN_ZOOM

# Half a pixel at the seam: 937 m. Douglas-Peucker guarantees no point moves
# further than this from where it was, so at the finest zoom this artifact
# draws at, nothing moves by half a pixel - and at the camera the app actually
# opens on (z2.2, App.tsx's UNITED_STATES_BOUNDS) it is a fourteenth of one.
OVERVIEW_SEAM_TOLERANCE_M = _metres_per_pixel(OVERVIEW_SEAM_ZOOM) / 2

# A trail whose WHOLE bounding box is under one pixel at the seam is not
# drawn, it is a dot - so it is dropped rather than simplified.
#
# MEASURED by running this function over the 136,941 records read back out of
# release 2026-09-16-4's own nearby_trails.geojson (2026-09-30): 110,077 of
# them - 80.4% - have a bounding box smaller than this, and dropping them with
# the tolerance above takes the artifact from 12,238,110 bytes to 1,811,212,
# or 14.8%.
#
# The prototype #1775 was argued from said 13.0%, applying one 937 m pass to
# the published sketch's 144,541 parts rather than 937 m to the 100 m pass
# above; composed Douglas-Peucker keeps a few more vertices. Both figures are
# in the issue and this one is the code's.
#
# The maintainer chose 1 px over 2 px by poll on 2026-09-30, from two frames
# drawn at the real opening camera: 2 px saved a further 590 KB and visibly
# thinned the haze, 1 px did not.
#
# WHY SIMPLIFICATION ALONE CANNOT DO THIS. Douglas-Peucker never drops a
# feature (simplify_records' own rule, and the silent-geometry-loss bug behind
# it), so it cannot go below two vertices per segment. Measured on the same
# file: 1,000 m leaves 309,570 vertices, 4,000 m leaves 290,333, and 8,000 m
# leaves 289,299 - an asymptote at two vertices times 144,541 segments,
# 5.3 MB, however coarse the tolerance is set. The cost here is segment
# COUNT, and only a floor reaches it.
#
# @unvalidated as a threshold, though the frames it was chosen from are real:
# nobody has looked at the opening camera on a phone in daylight, which is what
# would settle whether one pixel is the right floor. The same outdoor pass #105
# owes the rest of the map chrome.
OVERVIEW_MIN_FEATURE_M = _metres_per_pixel(OVERVIEW_SEAM_ZOOM)

# Three decimals, about 111 m of longitude here - an order finer than the
# tolerance above, which is export_trails.py's own precision rule applied to
# this artifact's own tolerance rather than to the 100 m one it no longer uses.
OVERVIEW_SEAM_DECIMALS = 3

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

# What write_overview keeps as its own named feature rather than folding into
# the generic (source, blaze_color, trail_status) haze (#1307).
#
# REASONED FROM THE ISSUE'S OWN TWO EXAMPLES, NOT MEASURED AGAINST THE LIVE
# REGISTRY. #1307 names the Long Path (~358 miles) and "a park loop" (under
# 10) as the two ends this threshold has to separate; nothing in this
# sandbox can fetch the live ArcGIS layers to measure the real distribution
# of named routes between them (no pipeline/data/raw/external here to sum -
# fetch_external_layers.py needs network access this environment does not
# have). 50 sits comfortably above a park loop and comfortably below the
# Long Path, which is everything the two examples actually pin down; where a
# trail the size of the Shawangunk Ridge Trail lands is genuinely unknown.
# What would settle it: running this against the live registry once
# fetchable, and reading the real gap between a park's longest loop and the
# shortest thing anyone would call a long-distance trail.
NAMED_TRAIL_THRESHOLD_MILES = 50.0

METERS_PER_MILE = 1609.344


def _miles(record: dict) -> float:
    """One record's real-world length, in miles.

    export_trails.py's own EPSG:5070 metric transform (_TO_METRIC), reused
    rather than a second way of measuring distance - that file's rule for
    simplification tolerance applies just as much to a threshold a trail is
    named or merged on either side of."""
    return shapely_transform(_TO_METRIC, shapely_wkt.loads(record["wkt"])).length / METERS_PER_MILE


def _miles_all(geoms: np.ndarray) -> list[float]:
    """`_miles` for every parsed geometry, as one reprojection and one length
    call (#1661): the same GEOS length of the same reprojected coordinates,
    divided the same way, so the same floats."""
    return (shapely.length(reproject(geoms, _TO_METRIC)) / METERS_PER_MILE).tolist()


# How close two rows must come to count as the same tread, in EPSG:5070
# metres like every other distance here.
#
# DERIVED FROM THE SIMPLIFICATION ABOVE, not picked. The records this reads
# have already been through OVERVIEW_SIMPLIFY_TOLERANCE_M, and
# Douglas-Peucker's guarantee is that no point moved further than the
# tolerance - so two rows that really did meet can now sit at twice it,
# one having moved that far each way. Anything less would let the
# simplification break chains that exist in the source.
#
# The answer does not turn on it, which is the more useful fact. Swept over
# release 2026-09-16-4's own 74,035 named usfs_trails rows (2026-09-30), from
# 17 m to 4,264 m - 250x - the qualifying count moves only between 79 and 87,
# and the count of qualifying routes spanning more than 5 degrees of longitude
# stays at 0 throughout. A threshold whose whole plausible range gives the
# same answer is not a threshold anybody has to defend.
CHAIN_TOLERANCE_M = 2 * OVERVIEW_SIMPLIFY_TOLERANCE_M

#: Where a record carries the trail it was found to be part of, set once after
#: qualification and read at grouping. Underscored because it is this module's
#: bookkeeping rather than anything a source published or an artifact carries.
_THROUGH_ROUTE_KEY = "_through_route_trail"

#: Which published spelling is which long trail, per source - the reviewed
#: half, in pipeline/reference/ because deciding that CDNST is the Continental
#: Divide Trail is a judgement somebody signs for (#1543, extended by #1776).
#: client/src/map/longTrailNames.ts is the same table on the client, and
#: tests/test_trail_name_aliases.py keeps the two in step.
TRAIL_ALIASES_PATH = ROOT / "reference" / "trail_name_aliases.json"


def _alias_index() -> dict[tuple[str, str], str]:
    """(source, published spelling) -> the trail's own name.

    Exact after the publisher's own spelling, never a prefix: USFS publishes
    "BARTRAM NRT - CHEOAH RD", and a road named after a trail is not it. That
    refusal is the alias table's, and this only reads it.
    """
    table = json.loads(TRAIL_ALIASES_PATH.read_text())
    return {
        (source, spelling): entry["trail"]
        for entry in table["trails"].values()
        for source, spellings in entry["published_as"].items()
        for spelling in spellings
    }


def _trail_identity(record: dict, aliases: dict[tuple[str, str], str]) -> tuple[str, str] | None:
    """(source, trail) for a record, or None where it names no trail.

    A published spelling the alias table knows becomes the trail's own name,
    so USFS's five spellings of the Continental Divide are one trail here
    rather than five - each qualifying separately today, and any of them whose
    rows fall under the threshold dropped into the haze while its siblings
    keep a casing. Everything else keeps the name its steward published.

    THE SOURCE STAYS IN THE KEY, which is #1307's own restraint and not this
    change's to spend: two organizations' trails that happen to share a name
    are never summed together. Folding it out was tried here and chained two
    stewards' 30-mile "Ridge Trail"s into one 60-mile through route - the
    defect this whole pass exists to remove, reintroduced one level up.
    """
    name = record.get("name")
    if name is None or not str(name).strip():
        return None
    source = record["source"]
    return source, aliases.get((source, name), name)


def _chain_labels(records: list[dict], tolerance_m: float) -> list[int]:
    """One label per record, equal where two records share tread.

    Union-find over every vertex, snapped to a `tolerance_m` grid, so the cost
    is linear in vertices rather than quadratic in records - this runs over
    136,941 of them. Any shared vertex joins, not only a shared endpoint: a
    long trail is commonly cut at an agency boundary rather than at its own
    junctions, so a row often meets the MIDDLE of its neighbour.

    Snapping to a grid means two points just either side of a cell edge do not
    meet. That is why the tolerance is twice what it strictly needs to be, and
    the sweep above is what says the residue does not matter.
    """
    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    metric = reproject(from_wkt_all([record["wkt"] for record in records]), _TO_METRIC)
    cells: dict[tuple[int, int], int] = {}
    for index, geometry in enumerate(metric):
        for x, y in shapely.get_coordinates(geometry):
            cell = (int(x // tolerance_m), int(y // tolerance_m))
            first = cells.setdefault(cell, index)
            if first != index:
                union(first, index)
    return [find(index) for index in range(len(records))]


def _through_routes(records: list[dict]) -> dict[int, str]:
    """Index of every record on a qualifying through route, to its trail's name.

    WHAT #1307 ASKED FOR AND WHAT IT GOT (#1776). The rule was "a trail whose
    segments total at least NAMED_TRAIL_THRESHOLD_MILES", summed per
    (source, name) so that two organizations' trails sharing a name were never
    added together. Inside ONE organization it still summed every row with the
    same name - and usfs_trails is one organization covering the country,
    where a trail name is not unique and never was. Measured against release
    2026-09-16-4's published artifact on 2026-09-30: 146 usfs_trails names
    cleared the threshold and 75 of them were spread over more than 5 degrees
    of longitude, which no single trail is. "GREEN MOUNTAIN" was 27 unrelated
    trails in 27 national forests, summed to 82 miles and drawn with the
    casing and the badge the Long Path was given, across 50.5 degrees - the
    width of the country.

    SO A TRAIL IS A RUN OF SHARED TREAD, not a spelling. Rows are chained
    where they touch, within one trail identity, and each CHAIN is measured
    against the threshold. That is what "one trail" means, and it needs no
    threshold on how far a name may spread: on the same data every one of
    those 146 names that spanned the country falls out, 81 features qualify,
    and none spans more than 2.9 degrees - the Appalachian Trail's own share
    of Virginia.

    IT IS CHAINED WITHIN AN IDENTITY RATHER THAN ACROSS THE SOURCE, and that
    boundary is load-bearing. Chaining every named row regardless of spelling
    was tried on the same data and merged trails that merely cross: the
    Appalachian Trail came out at 514 miles having absorbed GLENWOOD HORSE and
    ALLEGHENY TRAIL, and one component reached 185 miles over 25 spellings by
    running the length of a trail NETWORK. In a network everything touches
    eventually. The name says which trail; the tread says whether it is one.

    WHAT IT COSTS, because it is not free: a section its publisher draws
    disconnected from the rest of its trail falls into the unnamed haze. On
    the same measurement that is 464 of the 2,139 miles carried by the eight
    names the issue lists as real - and it is still DRAWN, at haze weight,
    just not cased or badged. The alias table is what recovers most of it, by
    making five spellings of one trail one identity before any of this runs.
    """
    aliases = _alias_index()
    # Each named record's own index in `records`, carried alongside, so the
    # answer can be returned against the caller's list however this one is
    # filtered and regrouped below.
    named: list[tuple[int, dict, tuple[str, str]]] = []
    for index, record in enumerate(records):
        trail = _trail_identity(record, aliases)
        if trail is not None:
            named.append((index, record, trail))
    if not named:
        return {}

    miles = _miles_all(from_wkt_all([record["wkt"] for _, record, _ in named]))

    by_trail: dict[tuple[str, str], list[int]] = {}
    for position, (_, _, trail) in enumerate(named):
        by_trail.setdefault(trail, []).append(position)

    qualifying: dict[int, str] = {}
    for trail, members in by_trail.items():
        labels = _chain_labels([named[position][1] for position in members], CHAIN_TOLERANCE_M)
        chains: dict[int, list[int]] = {}
        for position, label in zip(members, labels):
            chains.setdefault(label, []).append(position)
        for chain in chains.values():
            if sum(miles[position] for position in chain) >= NAMED_TRAIL_THRESHOLD_MILES:
                for position in chain:
                    qualifying[named[position][0]] = trail[1]
    return qualifying


def _above_the_seam_floor(records: list[dict]) -> list[dict]:
    """`records` without the ones too small to be a line at OVERVIEW_SEAM_ZOOM.

    The test is the whole record's bounding-box diagonal against
    OVERVIEW_MIN_FEATURE_M - one pixel at the seam - rather than its length,
    deliberately: a two-mile trail folded into three switchbacks inside one
    pixel draws as the same dot a 300 m spur does, and length would keep it.
    What the sketch is for is the SHAPE of the network at a continental
    camera, and a shape smaller than a pixel has none.

    A QUALIFYING NAMED TRAIL IS NEVER DROPPED, whatever its rows measure. The
    through-routes are the one thing #1307 and #1586 deliberately put on this
    camera - the Long Path beside the A.T., "make sure that all long distance
    trails get the same prominence as what the AT has now" - and a trail
    published as many short sections would otherwise be erased section by
    section while a single-row trail of the same length survived. That is the
    Long Path's own shape: 43 section records as of #1019's measurement.

    WHICH RECORDS THOSE ARE IS READ OFF THE RECORD, not looked up by name.
    Since #1776 two rows can carry one name and belong to different runs of
    tread, one a through route and one not, so a name is no longer enough to
    answer this - `_through_routes` decides it and leaves the answer on each
    record under `_THROUGH_ROUTE_KEY`.

    In EPSG:5070 metres, like every other distance this export takes, which is
    equal-area rather than conformal - so a "pixel" here is a few percent off
    a screen pixel across CONUS. Consistency with `simplify_records`' own
    tolerance is worth more than that, since the two are compared.
    """
    if not records:
        return []
    projected = reproject(from_wkt_all([record["wkt"] for record in records]), _TO_METRIC)
    bounds = shapely.bounds(projected)
    spans = np.hypot(bounds[:, 2] - bounds[:, 0], bounds[:, 3] - bounds[:, 1]).tolist()
    kept = []
    for record, span in zip(records, spans):
        if record.get(_THROUGH_ROUTE_KEY) is not None or span >= OVERVIEW_MIN_FEATURE_M:
            kept.append(record)
    return kept


def network_line_sources(registry: dict) -> list[dict]:
    """The external-organization entries that carry trail LINES.

    The same blaze-metadata marker export_trails.py's load_line_sources() uses,
    intersected with the external kinds rather than subtracted from them - so
    one marker means "this is a trail-line source" across both exports, and
    `kind` alone decides which of the two picks it up. An external layer that
    is not lines (OPRHP's facilities points, its park polygons) carries no
    blaze keys and is skipped here without needing to be named.

    ASKS `external_sources()` RATHER THAN THE ARCGIS HALF (#1432), because
    New York City's two walking-path layers are trail lines that arrive from
    a Socrata portal instead of a FeatureServer. They are the same kind of
    thing to every line below this one - a steward's segments, with a name
    and a blaze marker - and the transport they came in on is settled by the
    time this function is called. Reading only the ArcGIS half here is what
    would have made registering NYC a no-op at the export.
    """
    return [s for s in external_sources(registry) if "blaze_field" in s or "blaze_default" in s]


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
    if raw is None:
        return NEUTRAL_FALLBACK, "absent"

    # A BLANK STRING GETS ASKED OF THE REVIEWED TABLE BEFORE IT FALLS THROUGH
    # (#1207). Until the White Mountains arrived, every blank was the same
    # thing - a row whose publisher had not filled the column in - so this
    # returned Unknown ("Blaze not recorded") without looking.
    #
    # NH GRANIT was the case that needed it: its BLAZE was blank on 7,574 of
    # 7,643 Whites rows, and the blank was CORRECT rather than missing - the
    # White Mountains largely do not use paint blazes - so its table mapped
    # the blank to "None" ("Unblazed"). GRANIT dropped the column in
    # September 2026 (#1646) and the source was removed altogether (#1711),
    # so no table maps a blank today and every blank falls through to
    # Unknown. The path stays because the judgement it encodes - a blank a
    # publisher means is a fact, not a gap - belongs in a reviewed table
    # (reference/blaze_mapping.json) whenever a source earns it again.
    if isinstance(raw, str) and not raw.strip():
        mapped, disposition = map_source_blaze(raw, mapping)
        return (mapped, "mapped") if disposition == "mapped" else (NEUTRAL_FALLBACK, "absent")

    return map_source_blaze(raw, mapping)


#: How much of a line has to fall inside `boundary_source`'s polygons before it
#: counts as being in the park (#1533). @unvalidated as a threshold - what is
#: measured is what it decides: at 0.8, the ten reviewed drive names keep 12.02
#: miles inside Central and Prospect Park and drop the 0.39 miles of the same
#: names that run on outside them. A whole-containment test (1.0) would throw
#: away a drive whose last few metres cross the park edge at an entrance, and a
#: mere-intersection test (anything at 0) would keep a city street that only
#: clips a corner. What would settle it is a case where a real drive sits
#: between the two, which none of the ten does.
INSIDE_BOUNDARY_MIN_FRACTION = 0.8


def inside_boundary(geometry, boundary) -> bool:
    """Whether most of `geometry`'s length lies inside `boundary`.

    Measured in DEGREES rather than projected metres, which is sound here and
    would not be everywhere: the answer is a RATIO of two lengths of the same
    line within one park, so the lon/lat scale factor divides out almost
    exactly. It would not divide out if the two lengths came from different
    latitudes, which over a few hundred metres they cannot.

    A zero-length line is not inside anything - `_line_parts` already records
    what a degenerate line does to a map - and saying so here keeps the
    division below from being the thing that decides it.
    """
    length = geometry.length
    if not length:
        return False
    return geometry.intersection(boundary).length / length >= INSIDE_BOUNDARY_MIN_FRACTION


def load_boundary(source: dict):
    """The polygons `source` names in `boundary_source`, unioned - or None
    where it names none, which is every source but one today.

    `boundary_names` narrows the layer to particular parks by the `signname`
    its boundary layer publishes; without it the whole layer is the boundary.
    A named layer that is not on disk is an error rather than an empty
    boundary, for the reason export_nearby_poi.boundary_paths_for gives about
    the same key: a boundary that silently resolves to nothing turns a
    reviewed, narrow list into whatever the name filter happened to match.
    """
    key = source.get("boundary_source")
    if not key:
        return None

    path = RAW_DIR / f"{key}.geojson"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing, and {source['key']} names it in boundary_source - "
            "run fetch_external_layers.py first. Without it this source cannot be cut to the parks it is about."
        )

    wanted = source.get("boundary_names")
    polygons = [
        shape(feature["geometry"])
        for feature in json.loads(path.read_text(encoding="utf-8")).get("features", [])
        if feature.get("geometry") and (wanted is None or (feature.get("properties") or {}).get("signname") in wanted)
    ]
    if not polygons:
        raise SystemExit(
            f"{source['key']} names boundary_source {key!r} with boundary_names {wanted!r}, "
            f"and no polygon in {path} matches. Every row would be dropped."
        )
    return unary_union(polygons)


def keep_reason(source: dict, properties: dict, geometry, owned: dict[str, str], boundary=None) -> str | None:
    """None if this feature ships, else the reason it does not - a short string
    main() counts and prints. Every drop is one of these; there is no path out
    of this function that discards a feature without naming why.

    NO SOURCE IS LIMITED BY GEOGRAPHY HERE, since #1019. Two tests used to: a
    bounding box around New York City and an exclusion of OPRHP's `Long
    Island` region. Both are gone by the maintainer's decision of 2026-08-25
    (quoted in this module's docstring), and nothing has brought them back.

    `boundary` IS NOT THAT TEST COMING BACK, and the difference is worth
    stating because the two look alike from outside (#1533). A geographic clip
    asks "is this org's trail inside a region we chose to ship", and the answer
    was that an organization's layer ships whole. This asks "is this row one of
    the rows a reviewed list is ABOUT" - `nyc_park_drives` names ten street
    names in two boroughs that are car-free park drives, and the same names
    outside those two parks are ordinary city streets carrying cars. The
    boundary is the list's own definition rather than a limit on it, which is
    why it is set per source in `boundary_source` and why only a source that
    names one is asked the question at all."""
    if geometry is None or geometry.is_empty:
        return "no geometry"

    if boundary is not None and not inside_boundary(geometry, boundary):
        return "outside the boundary its registry entry names"

    foot_field = source.get("foot_field")
    if foot_field and properties.get(foot_field) not in source.get("foot_allowed", FOOT_ALLOWED_DEFAULT):
        return f"not a foot trail: {foot_field}={properties.get(foot_field)!r}"

    # The other direction (#1207). `foot_field` asks "does this row SAY it
    # is walkable" and drops everything that does not - right where the
    # column is populated, destructive where it is not, because an absent use
    # flag is unrecorded rather than a prohibition. `excluded_when` drops on
    # a POSITIVE assertion instead: a row whose steward says it is motorized,
    # or says hiking is not allowed. Acting on an assertion is sound where
    # acting on an absence is not - the maintainer's "It's OurHike, not
    # OurBike" applied with the evidence each layer actually offers. Three
    # sources use it (#1711): usfs_trails on `terra_motorized`, and the two
    # New Jersey layers on their motorized and hiking columns. Each entry's
    # `excluded_when_comment` in sources.json carries the measurement.
    for field, values in (source.get("excluded_when") or {}).items():
        if properties.get(field) in values:
            return f"excluded use: {field}={properties.get(field)!r}"

    status_field = source.get("status_field")
    if status_field and properties.get(status_field) not in SHIPPED_STATUSES:
        return f"status not shipped: {properties.get(status_field)!r}"

    name_field = source.get("name_field", "Name")
    if suppressed_by_owner(source["key"], properties.get(name_field), owned):
        return f"route owned by {owned[str(properties.get(name_field)).strip()]}"

    return None


def missing_declared_fields(source: dict, features: list[dict]) -> list[str]:
    """The fields a registry entry names that appear on NO fetched feature.

    WHY THIS EXISTS (#1646). Every filter in keep_reason() reads a column by
    the name sources.json gives it, and `properties.get(name)` on a column
    that does not exist returns None rather than failing. So when NH GRANIT
    republished its trails layer in September 2026 and renamed SNOWMBL/ATV
    to SNOWMACHIN/OHRV, `excluded_when` matched nothing, every snowmobile
    corridor in the state shipped as a hiking trail, and the run was green -
    measured 2026-09-26, 2,375 mi of motorized-only corridor in the
    published release, and the #1646 mileage jump nobody could explain. A
    column that is null on every row is a data question; a column that is
    ABSENT from every row is the registry describing a layer that no longer
    exists, and that is a stop.

    Only the keys the entry states are checked - `name_field`'s "Name"
    default is not, because a source that never declared it never claimed
    the column."""
    declared = [source.get(key) for key in ("name_field", "foot_field", "blaze_field", "status_field")]
    declared += list(source.get("excluded_when") or {})
    present: set[str] = set()
    for feature in features:
        present.update((feature.get("properties") or {}).keys())
    return [field for field in dict.fromkeys(declared) if field and field not in present]


def declared_name(source: dict, properties: dict):
    """One feature's name, or None where the steward published a PLACEHOLDER.

    WHY THIS EXISTS (#1432). NYC Parks fills `trail_name` on every row, and on
    3,775 of 7,059 - 53% - what it fills it with is `Unnamed Official Trail`,
    `Name TBD` or `TBD`. Those are the steward saying "no name", in a column
    that cannot be empty, and reading them as names is a display outrunning
    its source: measured on the live layer, `Unnamed Official Trail` totals
    128.7 miles, which clears NAMED_TRAIL_THRESHOLD_MILES and would have
    shipped ONE overview feature named "Unnamed Official Trail", marked
    `through_route: true`, drawn at through-route weight across five boroughs
    beside the Appalachian Trail - and labelled that on the map and in every
    tapped-line sheet.

    So a source may declare `name_placeholders`, and a value in that list is
    treated exactly as an absent name. CLAUDE.md's rule is the one being
    applied: "Omit rather than guess... Absent means unknown, never zero and
    never 'none'." The registry entry carries the measured counts, and
    `park_name` is what a screen should fall back to for these rows - a
    display decision that belongs to features/NEARBY_TRAILS.md, not here.

    Matched case-insensitively on the stripped value, because a placeholder
    is prose typed by whoever surveyed the segment rather than a coded domain.

    `name_constant` IS THE SAME RULE POINTING THE OTHER WAY (#1778). Some
    stewards publish one trail as a layer with no name column at all: PCTA's
    `PCTA_Centerline` is a single feature with two fields, `OBJECTID` and
    `Shape__Length`. The trail's name is not missing from that layer, it is
    the layer - and dropping it into the unnamed haze would be as wrong as
    reading `Name TBD` as a name. So a source may declare `name_constant`, and
    every feature it ships carries that name.

    THE REGISTRY HAS TO EARN IT, because this is the one place the pipeline
    writes a name no steward published. A row carrying `name_constant` records
    the measurement that identifies the trail, and the three registered under
    #1778 were each checked end to end on 2026-09-30 before the name was
    written: PCTA's one feature is 2,653 miles from 32.59 deg N to 49.00 deg N -
    Mexico to Canada, against the PCT's published 2,650 - and CDTC's eight
    total 3,060 miles from 31.50 to 49.05 against the CDT's 3,028. Wisconsin
    DNR's single `Ice Age Trail` feature is 711 miles, which is the BUILT
    segments of a trail planned at about 1,200, and its row says so rather
    than implying the whole route is there.

    A source may not declare both: `name_field` says where to read the name
    and `name_constant` says there is nowhere to read it, so a row claiming
    both has not decided what it is. `name_constant_conflicts` below is the
    check, and it runs over the registry rather than per feature.
    """
    constant = source.get("name_constant")
    if constant is not None:
        return constant
    raw = properties.get(source.get("name_field", "Name"))
    placeholders = source.get("name_placeholders")
    if not placeholders or raw is None:
        return raw
    if str(raw).strip().casefold() in {str(p).strip().casefold() for p in placeholders}:
        return None
    return raw


def name_constant_conflicts(sources: list[dict]) -> list[str]:
    """The registry keys that declare both a name column and a name constant.

    A stop rather than a warning, on missing_declared_fields' own argument: a
    row that says both has not decided which is true, and `declared_name`
    would silently take the constant and never read the column - so the
    column's name would sit in the registry looking enforced while nothing
    read it, which is the decoration `usfs_trails`' own entry records having
    removed once already.
    """
    return [s["key"] for s in sources if s.get("name_constant") is not None and s.get("name_field") is not None]


def build_records(source: dict, features: list[dict], owned: dict[str, str], boundary=None) -> tuple[list[dict], dict]:
    """One source's shippable features as export_trails.py-shaped records
    (id/source/name/blaze_color/trail_status/wkt), plus a stats dict of what
    was dropped and why."""
    key = source["key"]
    mapping = load_blaze_mapping().get(key)
    status_field = source.get("status_field")

    records: list[dict] = []
    drops: dict[str, int] = {}
    blazes: dict[str, int] = {}

    for index, feature in enumerate(features):
        properties = feature.get("properties") or {}
        raw_geometry = feature.get("geometry")
        geometry = shape(raw_geometry) if raw_geometry else None

        reason = keep_reason(source, properties, geometry, owned, boundary)
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
                "name": declared_name(source, properties),
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


def declared_duplicate_pairs(sources: list[dict]) -> list[tuple[str, str]]:
    """The (senior, junior) source pairs a registry entry declares (#1459).

    Declared rather than derived, one pair at a time, by somebody who has
    looked at the measurement for that pair - lib/duplicates.py says why.
    A junior naming a senior this export is not shipping is skipped rather
    than raising: a steward held back by `reaches_hikers` must not take the
    other one's lines down with them.
    """
    shipping = {source["key"] for source in sources}
    return [
        (source["duplicate_of"], source["key"])
        for source in sources
        if source.get("duplicate_of") and source["duplicate_of"] in shipping
    ]


def deduplicate(records: list[dict], pairs: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """`records` with each declared pair's duplicates removed, plus the stats.

    Pairs are applied in order against the records still standing, so a
    source that is junior in one pair and senior in another sees the first
    pair's result. No such chain exists today and the ordering is stated so
    that adding one is a decision rather than an accident.
    """
    stats: list[dict] = []
    for senior_key, junior_key in pairs:
        senior = [r for r in records if r.get("source") == senior_key]
        junior = [r for r in records if r.get("source") == junior_key]
        duplicates, pair_stats = find_duplicates(senior, junior)
        records = apply_duplicates(records, duplicates)
        stats.append({"senior": senior_key, "junior": junior_key, **pair_stats})
    return records, stats


def closure_area_sources(registry: dict) -> list[dict]:
    """The registered layers that publish CLOSED AREAS rather than trail lines
    (#964). NYS Parks' temporary closures is the first and only one today.

    Selected on the `closure_areas` marker and asked of `external_sources()`,
    so a steward who publishes closures somewhere other than ArcGIS is picked
    up by declaring the marker rather than by editing this line (#1432).
    Neither New York City layer declares it - the city publishes no closure
    state at all, which is a gap and not a silence this reads as "open"."""
    return [s for s in external_sources(registry) if s.get("closure_areas")]


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
    goes nowhere near the closure. A band across a trail that is open is a
    cry-wolf failure on a mark a hiker is meant to obey without checking -
    the same false-positive cost this codebase's safety paths generally
    treat as worse than a miss (CLAUDE.md, "Miss rather than cry wolf").

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


def _rounded_geometries(geoms: np.ndarray) -> list[dict]:
    """`_rounded_geometry` for every geometry (#1661): one rounding pass over
    every coordinate and one drawability test per part, where the
    per-record function walked `__geo_interface__` and called `round` twice
    per vertex. On the real network records_to_geojson spent 54.1 s doing
    that record by record - a parse, `_miles`, this walk - and 16.3 s this
    way, under the profiler (2026-09-24).

    Only non-empty 2D LineStrings and MultiLineStrings take the array path
    (export_trails._flat_lines); anything else is handed to
    `_rounded_geometry` itself."""
    out: list = [None] * len(geoms)
    flat = _flat_lines(geoms)
    for index in np.flatnonzero(~flat).tolist():
        out[index] = _rounded_geometry(geoms[index])
    selected = np.flatnonzero(flat)
    parts, owner = shapely.get_parts(geoms[selected], return_index=True)
    counts = shapely.get_num_coordinates(parts)
    coords = shapely.get_coordinates(parts)
    decimals = NEARBY_COORDINATE_DECIMALS
    rounded = np.column_stack((round_like_python(coords[:, 0], decimals), round_like_python(coords[:, 1], decimals)))
    # _drawable_after_cut, for every part at once: two distinct vertices once
    # cut is the same as some vertex differing from the part's first. A
    # geometry is cut only if every one of its parts survives the cut.
    part_of = np.repeat(np.arange(len(parts)), counts)
    first = np.cumsum(counts) - counts
    survives = np.zeros(len(parts), dtype=bool)
    survives[part_of[(rounded != rounded[first[part_of]]).any(axis=1)]] = True
    cut = np.bincount(owner[~survives], minlength=len(selected)) == 0
    chosen = np.where(np.repeat(cut[owner], counts)[:, None], rounded, coords).tolist()

    is_multi = (shapely.get_type_id(geoms[selected]) == 5).tolist()
    start = 0
    for position, end in zip(owner.tolist(), np.cumsum(counts).tolist()):
        index = int(selected[position])
        if is_multi[position]:
            if out[index] is None:
                out[index] = {"type": "MultiLineString", "coordinates": []}
            out[index]["coordinates"].append(chosen[start:end])
        else:
            out[index] = {"type": "LineString", "coordinates": chosen[start:end]}
        start = end
    return out


def records_to_geojson(records: list[dict]) -> dict:
    """The FeatureCollection the client draws. Properties only - no geometry
    re-derivation - so what is written is what was clipped and simplified,
    at the precision NEARBY_COORDINATE_DECIMALS caps."""
    geoms = from_wkt_all([record["wkt"] for record in records])
    features = []
    for record, length_miles, geometry in zip(records, _miles_all(geoms), _rounded_geometries(geoms)):
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": record["id"],
                    "source": record["source"],
                    "name": record["name"],
                    "blaze_color": record["blaze_color"],
                    # THIS RECORD'S OWN LENGTH, and the only thing that lets a
                    # phone tell a whole trail from part of one (#1516).
                    #
                    # client/src/lib/lineClimb.ts compares the edges it holds
                    # against this number: materially shorter means the line
                    # runs past the cells downloaded, so the climb it could sum
                    # would be silently low. Without the field that comparison
                    # has nothing to stand on and the phone cannot refuse to
                    # answer - which is what shipped in v1.3.0, where
                    # lineClimb's own header said this exporter wrote the field
                    # and it did not.
                    #
                    # MEASURED FROM THE GEOMETRY BEING PUBLISHED, not from a
                    # steward's stated mileage, and the difference matters both
                    # ways. It is the right number, because it describes the
                    # same clipped and simplified line the phone is holding
                    # edges of - a steward's own figure measures ground this
                    # artifact may have clipped at a state border. It is also
                    # NOT the steward's claim, so nothing downstream may
                    # present it as one.
                    #
                    # `_miles` is export_trails.py's EPSG:5070 transform, the
                    # one this file already names a trail and merges a
                    # duplicate on either side of - one way of measuring
                    # distance, not a second. `_miles_all` is it for every
                    # record at once.
                    "length_miles": round(length_miles, 2),
                    # Every record this export builds carries a status. A
                    # shared-ground pair's A.T. half (#1384) carries none,
                    # because trails.geojson publishes none for the A.T. -
                    # absent means unknown, never invented open.
                    **({"trail_status": record["trail_status"]} if "trail_status" in record else {}),
                    # Only on a closed record, and only when the steward said
                    # something. Omitted rather than null everywhere else -
                    # 3,663 features do not need three empty keys each, and an
                    # absent key reads as "no reason given" the same way an
                    # absent capacity does on a shelter.
                    #
                    # `closure_source` is the CLOSURE layer's registry key,
                    # not the line's `source`: an area closure can land on
                    # another organization's trail, and the sheet must not
                    # read OPRHP's closure in NYNJTC's name (#1142). It was
                    # set on every area record since #964 and never shipped -
                    # the client-side half of that finding.
                    **({"closure_kind": record["closure_kind"]} if record.get("closure_kind") else {}),
                    **({"closure_reason": record["closure_reason"]} if record.get("closure_reason") else {}),
                    **({"closure_source": record["closure_source"]} if record.get("closure_source") else {}),
                    # Only on a record that swallowed another organization's
                    # copy of the same path (#1459): whose copy it was.
                    #
                    # SHIPPED THOUGH NOTHING READS IT YET, and that is the
                    # correction rather than an oversight. lib/duplicates.py
                    # says the loser "is kept on the survivor rather than
                    # discarded", features/POI_DEDUPLICATION.md §3's "a line
                    # in the identity ledger, not a new file" - and the field
                    # was set on 271 records and dropped here, so the claim
                    # was true of the pipeline and false of everything a
                    # reader could see. `closure_source` was the same finding
                    # (#1142): set on every area record since #964 and never
                    # shipped. A merge that cannot be seen from the artifact
                    # is a merge nobody can check.
                    **({"duplicate_of": record["duplicate_of"]} if record.get("duplicate_of") else {}),
                    # Only on a shared-ground pair (#1384): the other trail's
                    # name and source, and which side of the chord this half is.
                    **({"concurrent_with": record["concurrent_with"]} if record.get("concurrent_with") else {}),
                    **({"concurrent_source": record["concurrent_source"]} if record.get("concurrent_source") else {}),
                    **({"concurrent_side": record["concurrent_side"]} if record.get("concurrent_side") else {}),
                },
                "geometry": geometry,
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
    bounds = shapely.bounds(from_wkt_all([record["wkt"] for record in records])).tolist()
    return [
        min(b[0] for b in bounds),
        min(b[1] for b in bounds),
        max(b[2] for b in bounds),
        max(b[3] for b in bounds),
    ]


def write_overview(records: list[dict]) -> dict:
    """Write the corridor-view sketch of the network to OUT_DIR, and return its
    manifest entry (#1135).

    Takes the SAME records write_artifact publishes - after every filter, the
    closure split and the 1 m simplification - so the sketch can never describe
    different trails: it is those lines with vertices removed, and now also
    with the ones too small to draw at its own top zoom removed outright.

    IT HAS ITS OWN CONSTANTS SINCE #1775, where it used to import
    export_trails.py's (100 m Douglas-Peucker, four decimals). The two sketches
    stopped answering the same question when #1615 cut the tiles from z5: the
    A.T.'s overview still draws to CORRIDOR_MAX_ZOOM and its 100 m is reasoned
    from the pin seam's pixel and from a safety argument about a line drawn
    where it does not go, while THIS sketch now hands the network to the tiles
    at OVERVIEW_SEAM_ZOOM and only owns z0-z5. Sharing one tolerance across
    two artifacts with different top zooms is what made this one 16 times finer
    than it draws - so the drift the shared import was preventing is now the
    thing to prevent, and export_trails.py's constant must not follow this one.

    ONE FEATURE PER (source, blaze_color, trail_status), where the A.T.'s
    overview is one feature flat. The first two are the properties the client's
    line expressions read (map/style.ts keys width and ghosting off `source`,
    colour off `blaze_color`), so the sketch draws through the same paint as
    the real lines. `trail_status` is the safety column: 224 of 21,805 features
    read `closed` (measured 2026-08-27), and folding closed ground into an
    `open` feature would draw it open-looking at the one range of zooms where
    the full artifact's own tape does not draw - the display outrunning its
    source. Measured cost of carrying it: 25 -> 31 features, +328 gzipped
    bytes. `closure_kind` and `closure_reason` deliberately do not ride along:
    the sketch is paint and tape, and the sheet that reads those opens on the
    real lines above the seam.

    EXCEPT WHERE A NAME EARNS ITS OWN FEATURE (#1307). "Only the AT shows
    initially. All the long distance trails should show. At least the
    LongPath should be visible" - the maintainer, on the opening camera this
    sketch draws. A source's rows sharing one NAME_TRAIL_THRESHOLD_MILES's
    worth of real length on ONE RUN OF SHARED TREAD (_through_routes, in miles
    over export_trails.py's own EPSG:5070 transform) keep that trail's name
    and a `through_route: true` flag
    instead of folding into the (source, blaze_color, trail_status) haze - so
    map/trailsInView.ts can badge them the same way it already badges the
    A.T. (TAPPABLE_BLAZE_LAYER_IDS), and map/style.ts can draw them at their
    own weight (NETWORK_OVERVIEW_THROUGH_ROUTE_FAR_WIDTH) instead of the
    generic dot haze's. Everything under the threshold, and everything with
    no name at all, groups exactly as before - this is an exception to ONE
    FEATURE PER above, not a replacement for it.

    WHAT IT WEIGHS. The figure this docstring carried for a year - 480,115 ->
    57,226 coordinates, 1,125,263 bytes raw, 255,263 gzipped, measured
    2026-08-27 by pipeline/spike_network_overview.py, whose method this
    function is - described a network of five stewards. It is eleven now, and
    the same code had grown to 616,517 coordinates and 12,238,110 bytes in
    release 2026-09-16-4. That is the growth #1775 is about: the sketch was the
    ONE launch fetch whose size followed the number of organizations, and 71.3%
    of it was a single nationwide source's.

    Re-measured 2026-09-30 by running THIS function over the 136,941 records
    read back out of that release's own nearby_trails.geojson, first when
    #1775 cut it and again once #1776 changed what qualifies:

                              shipped      #1775      #1776
        records kept          136,941     26,864     25,350
        coordinates           616,517     98,948     95,854
        raw bytes          12,238,110  1,811,212  1,735,301
        gzipped             3,344,736    407,480    393,227
        features                  201        188         93
        through routes            142        142         47

    THE FEATURE COUNT HALVES AND ALMOST NO BYTES GO WITH IT, which is the
    shape of #1776 rather than a disappointment: what stopped being a named
    feature did not stop being drawn, it folded back into the haze group it
    always belonged in. 95 fewer features for 76 KB is the sketch saying less
    about lines it was never entitled to name.

    14.8%. The prototype #1775 was argued from said 13.0%, applying one
    937 m pass to the published sketch; this code applies 937 m to the 100 m
    pass above, and composed Douglas-Peucker keeps a few more vertices than a
    single coarser one. The prototype's figure is the one to distrust - it was
    not this code.

    Re-run it rather than trusting this paragraph: the numbers move with every
    source the registry gains, and that they move LESS than linearly now is the
    whole point of the floor.
    """
    coarse = simplify_records(records, OVERVIEW_SIMPLIFY_TOLERANCE_M)

    qualifying = _through_routes(coarse)
    for index, record in enumerate(coarse):
        record[_THROUGH_ROUTE_KEY] = qualifying.get(index)

    # QUALIFICATION IS MEASURED BEFORE THE RESIZE AND IS UNCHANGED BY IT
    # (#1775). The 100 m pass above is still what _through_routes reads, so
    # measuring a trail's length off the 937 m simplification below cannot
    # shorten a switchbacked one enough to cost it its own feature and its
    # casing. Since #1776 the same applies to the CHAINING: at 937 m the seam
    # geometry would join tread that never meets.
    #
    # Then the floor, then the seam tolerance, in that order: dropping first
    # means the second simplification only walks the segments that survived.
    # Simplifying twice is not the same as simplifying once at the sum, but
    # Douglas-Peucker's guarantee composes - no point has moved further than
    # 100 + 937 m from where it started, which is under a pixel and a half at
    # the seam and a fourteenth of one at the opening camera.
    kept = _above_the_seam_floor(coarse)
    seam = simplify_records(kept, OVERVIEW_SEAM_TOLERANCE_M)

    # The group key is always this four-tuple, name "" standing for "not a
    # qualifying named trail" - never None, which would make sorted() below
    # compare a string against a NoneType and raise. feature_properties()
    # reads the sentinel back into "omit name and through_route entirely",
    # this export's existing convention for closure_kind above.
    groups: dict[tuple[str, str, str, str], list[list[list[float]]]] = {}
    coarse_lines = _overview_coordinates_all(from_wkt_all([record["wkt"] for record in seam]), OVERVIEW_SEAM_DECIMALS)
    for record, lines in zip(seam, coarse_lines):
        # THE NAME WRITTEN IS THE TRAIL'S, not the spelling the steward
        # published: USFS's "PCT: MT HOOD" and "PCNST" are both the Pacific
        # Crest Trail, and a map labelling one of them "PCNST" has told a
        # hiker less than it knows. client/src/map/longTrailNames.ts folds the
        # same table, so a badge still resolves - and the trail's own name is
        # already one of the spellings that table lists.
        #
        # `_THROUGH_ROUTE_KEY` rides the record rather than being looked up
        # again here, because this list is two transformations downstream of
        # the one qualification measured: the floor dropped rows and both
        # simplifications returned copies. Re-deriving it would mean chaining
        # the seam geometry, which is 937 m coarse and would join tread that
        # does not meet.
        key = (
            record["source"],
            record.get(_THROUGH_ROUTE_KEY) or "",
            record["blaze_color"],
            record["trail_status"],
        )
        groups.setdefault(key, []).extend(lines)

    def feature_properties(key: tuple[str, str, str, str]) -> dict:
        source, name, blaze, status = key
        properties = {"source": source, "blaze_color": blaze, "trail_status": status}
        if name != "":
            properties["name"] = name
            properties["through_route"] = True
        return properties

    body = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": feature_properties(key),
                "geometry": {"type": "MultiLineString", "coordinates": lines},
            }
            for key, lines in sorted(groups.items())
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / OVERVIEW_ARTIFACT_NAME
    path.write_text(json.dumps(body, separators=(",", ":")))

    return {
        "path": to_manifest_path(path),
        "sha256": sha256_file(path),
        "feature_count": len(body["features"]),
        "coordinate_count": sum(len(line) for lines in groups.values() for line in lines),
        "tolerance_m": OVERVIEW_SEAM_TOLERANCE_M,
        "named_trail_threshold_miles": NAMED_TRAIL_THRESHOLD_MILES,
        # What the floor removed, so a reader can tell a sketch that shrank
        # because the network shrank from one that shrank because the floor
        # moved - the two look identical in a byte count alone.
        "seam_zoom": OVERVIEW_SEAM_ZOOM,
        "min_feature_m": OVERVIEW_MIN_FEATURE_M,
        "records_before_floor": len(coarse),
        "records_after_floor": len(kept),
    }


def write_tiles(geojson_path: Path, concurrent_path: Path | None = None) -> dict:
    """Tile the artifact just written into TILES_ARTIFACT_NAME and return its
    manifest entry (#1257).

    Cut from the written GeoJSON rather than from the records, so the tiles
    and the file cannot disagree about a vertex: ST_Read hands GDAL exactly
    the features and properties the file carries, and `SELECT *` keeps every
    property - the closure_* columns only exist on a run whose records hold a
    closed trail, and a hand-kept column list would fail the runs that do not.

    `concurrent_path` is the shared-ground pairs (#1384), unioned in BY NAME
    so each file's columns line up with the other's and a column only one of
    them has reads NULL on the other's rows - GDAL then writes no property
    for it, which is what the client's `has` filters read. Passed only when
    the file holds a feature: ST_Read of an empty collection is a table with
    no columns (lib/corridor.py's count_features has the failure), and there
    is nothing to union in.

    GDAL's PMTiles driver builds an MBTiles beside the output and converts it,
    so the run needs roughly the archive's own size again in scratch space
    while it runs, released when the COPY returns.

    Fails loudly if the header does not declare the zooms the client is
    built for: a creation option GDAL silently ignored would publish a
    tileset the map never asks the right zooms of, and the failure on the
    phone is an empty map with no error anywhere.
    """
    path = OUT_DIR / TILES_ARTIFACT_NAME
    # COPY TO refuses to overwrite for these drivers - export_trails.py's own
    # note - and this needs to be safely re-runnable.
    path.unlink(missing_ok=True)

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    lines = f"SELECT * FROM ST_Read('{geojson_path.as_posix()}')"
    if concurrent_path is not None:
        lines = f"{lines} UNION ALL BY NAME SELECT * FROM ST_Read('{concurrent_path.as_posix()}')"
    con.execute(
        f"""
        COPY ({lines})
        TO '{path.as_posix()}'
        WITH (
            FORMAT GDAL, DRIVER 'PMTiles', LAYER_NAME '{TILES_LAYER}',
            DATASET_CREATION_OPTIONS (
                'MINZOOM={TILES_MIN_ZOOM}', 'MAXZOOM={TILES_MAX_ZOOM}',
                'NAME={TILES_ARTIFACT_NAME.removesuffix(".pmtiles")}',
                'DESCRIPTION=Trail lines other organizations maintain, as vector tiles'
            )
        )
        """
    )

    with path.open("rb") as f:
        header = Reader(MmapSource(f)).header()
    zooms = (header["min_zoom"], header["max_zoom"])
    if zooms != (TILES_MIN_ZOOM, TILES_MAX_ZOOM):
        raise SystemExit(
            f"{path} declares zooms {zooms}, not the z{TILES_MIN_ZOOM}-z{TILES_MAX_ZOOM} the client is "
            "built for (client/src/lib/config.ts). GDAL did not honour the creation options, and a "
            "tileset the map asks the wrong zooms of draws nothing."
        )

    return {
        "path": to_manifest_path(path),
        "sha256": sha256_file(path),
        "layer": TILES_LAYER,
        "min_zoom": TILES_MIN_ZOOM,
        "max_zoom": TILES_MAX_ZOOM,
        "tile_count": header["addressed_tiles_count"],
    }


def load_at_centerline() -> list[dict]:
    """ATC's centerline as export_trails.py-shaped records, for the shared-
    ground pairing (#1384) - or [] with a loud line when the A.T. fetch is not
    there. See the SHARED GROUND block in the module docstring for why the raw
    file rather than the published one, and why the centerline alone.

    export_trails.py's own functions, in its own order up to the corridor
    clip: the clip and the chain merge change which vertices are published
    not where they are, and the pairing measures where. The centerline
    carries a flat `blaze_default` and no `blaze_field`, so normalising it
    makes no network call."""
    sources = [s for s in load_line_sources(AT_SOURCES_PATH) if s["key"] == AT_CENTERLINE_SOURCE]
    path = AT_RAW_DIR / f"{AT_CENTERLINE_SOURCE}.geojson"
    if not sources or not path.exists():
        print(
            f"  HELD BACK: shared ground is paired over the network alone - {path} is not there, "
            "and the A.T.'s share of it needs the centerline fetch_all.py writes. "
            "A run of the publish workflow has it; a checkout with only the external layers does not."
        )
        return []
    (source,) = sources
    records = build_trail_records(source, normalize_source_features(source, load_features(path)))
    return simplify_records(records)


def write_concurrent(pairs: list[dict], stats: dict, *, at_paired: bool) -> dict:
    """Write the shared-ground pairs beside the lines and return their manifest
    entry (#1384): the file, the pairing's own counts and constants, and
    whether the A.T. was in the pool - so a manifest can say "no shared
    ground" and "no A.T. to share it with" as two different things."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / CONCURRENT_ARTIFACT_NAME
    path.write_text(json.dumps(records_to_geojson(pairs), separators=(",", ":")))
    return {
        "path": to_manifest_path(path),
        "sha256": sha256_file(path),
        "feature_count": len(pairs),
        "at_paired": at_paired,
        **stats,
    }


def write_artifact(records: list[dict], per_source: dict) -> dict:
    """Write the artifact and return its manifest entry."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / ARTIFACT_NAME
    path.write_text(json.dumps(records_to_geojson(records), separators=(",", ":")))

    return {
        "path": to_manifest_path(path),
        "sha256": sha256_file(path),
        "feature_count": len(records),
        "bbox": exported_bbox(records),
        "sources": per_source,
    }


def _rss_mb() -> float | None:
    """This process's resident memory now, in MB, from /proc; None where there is no /proc."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def _progress(started: float, step: str) -> None:
    """One line before each pass after the closures step, which used to run silent (#1796).

    Seven passes ran between "closed area(s)" and the first write message with
    no output at all, and on runs 157, 158 and 160 the hosted runner was lost
    inside that span, so the log could not say which pass it was. Each line
    carries the elapsed time, this process's resident memory now and its peak
    so far (ru_maxrss is KiB on Linux), which is what tells a pass that is
    merely slow from one that is exhausting the machine.
    """
    now = _rss_mb()
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    rss = "unknown" if now is None else f"{now:,.0f} MB"
    print(f"  [{time.monotonic() - started:7.1f}s] {step} (rss {rss}, peak {peak:,.0f} MB)", flush=True)


def main() -> dict:
    registry = load_registry(SOURCES_PATH)
    sources = network_line_sources(registry)
    # Over the registry rather than per feature, and before anything is
    # fetched: a row claiming both a name column and a name constant is a
    # contradiction in the file, not a fault in the data (#1778).
    conflicts = name_constant_conflicts(sources)
    if conflicts:
        raise SystemExit(
            f"{', '.join(conflicts)}: sources.json declares both name_field and name_constant. "
            "declared_name takes the constant and never reads the column, so the column would sit "
            "in the registry looking enforced while nothing read it. Keep whichever is true."
        )
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
        # Before any filter runs, so a renamed column fails the run rather
        # than turning its filter into a no-op (#1646). An empty layer is
        # fail_if_incomplete()'s question, not this one.
        missing = missing_declared_fields(source, features) if features else []
        if missing:
            raise SystemExit(
                f"{key}: sources.json names {missing}, and none of the {len(features):,} fetched features carries "
                f"{'it' if len(missing) == 1 else 'them'}. The layer's schema has changed - re-read its fields "
                f"at {source.get('url')} and update the registry entry before exporting."
            )
        records, stats = build_records(source, features, owned, load_boundary(source))

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
    # One path two organizations each recorded, drawn once (#1459). BEFORE the
    # closures and the simplification, and both orders matter: a closure that
    # split a senior record would leave two halves for a junior to be judged
    # against, and simplify_records is what makes geometry final, so a
    # proximity test belongs on the geometry the sources actually published.
    duplicate_pairs = declared_duplicate_pairs(sources)
    if duplicate_pairs:
        before = len(all_records)
        all_records, duplicate_stats = deduplicate(all_records, duplicate_pairs)
        for pair in duplicate_stats:
            print(
                f"  {pair['junior']} against {pair['senior']}: {pair['duplicates']:,} duplicate(s) removed "
                f"({pair['junior_miles_removed']:.1f} mi) at {pair['tolerance_m']:.0f} m, "
                f"{pair['touched_but_kept']:,} near but under {pair['min_share']:.0%} and kept"
            )
        print(f"  {before:,} records -> {len(all_records):,} after deduplication")
    else:
        duplicate_stats = []

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
    passes_started = time.monotonic()
    try:
        total = next(line for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemTotal:"))
        print(f"  machine memory: {int(total.split()[1]) / 1024:,.0f} MB", flush=True)
    except (OSError, StopIteration):
        pass
    _progress(passes_started, f"simplifying {len(all_records):,} records")
    simplified = simplify_records(all_records)
    _progress(passes_started, "writing the network lines")
    manifest = write_artifact(simplified, per_source)
    manifest["closures"] = closure_stats
    manifest["duplicates"] = duplicate_stats
    # The shared-ground pairs (#1384), from the records just written plus the
    # A.T.'s centerline, into their own file - never into the one above, for
    # the eleven readers the module docstring counts.
    _progress(passes_started, "loading the A.T. centerline")
    at_records = load_at_centerline()
    _progress(passes_started, f"finding shared ground among {len(simplified) + len(at_records):,} lines")
    pairs, shared = find_shared_ground(simplified + at_records)
    _progress(passes_started, f"writing the shared ground ({len(pairs):,} pairs)")
    manifest["concurrent"] = write_concurrent(pairs, shared, at_paired=bool(at_records))
    # The corridor-view sketch, from the same simplified records the artifact
    # was just written from - export_trails.py's ordering, for its reason: the
    # overview simplifies the same geometry a second time at its own coarser
    # tolerance.
    _progress(passes_started, "writing the overview")
    manifest["overview"] = write_overview(simplified)
    # The same lines as vector tiles (#1257), cut from the file just written
    # so the two cannot disagree - see write_tiles for what a phone gains.
    # The pairs ride in the tiles, and only when there are any to ride.
    _progress(passes_started, "cutting the vector tiles")
    manifest["tiles"] = write_tiles(Path(manifest["path"]), Path(manifest["concurrent"]["path"]) if pairs else None)
    _progress(passes_started, "every pass done")

    size = Path(manifest["path"]).stat().st_size
    print(f"\n  {manifest['feature_count']:,} features -> {manifest['path']} ({size:,} bytes)")
    overview = manifest["overview"]
    print(
        f"  overview: {overview['feature_count']} features, {overview['coordinate_count']:,} coordinates "
        f"-> {overview['path']} ({Path(overview['path']).stat().st_size:,} bytes)"
    )
    concurrent = manifest["concurrent"]
    print(
        f"  shared ground: {concurrent['stretches']} stretches, {concurrent['shared_m'] / 1000:.1f} km, "
        f"{concurrent['feature_count']} pair features among {concurrent['trails']} trails"
        f"{'' if concurrent['at_paired'] else ' (network only)'} "
        f"(within {concurrent['tolerance_m']:g} m for {concurrent['min_length_m']:g} m or more; "
        f"{concurrent['dropped_short']} shorter pieces dropped, {concurrent['dropped_unpainted']} with no blaze to paint, "
        f"{concurrent['dropped_same_blaze']} in one paint, {concurrent['nameless_skipped']} nameless lines skipped) "
        f"-> {concurrent['path']}"
    )

    tiles = manifest["tiles"]
    print(
        f"  tiles: {tiles['tile_count']:,} tiles z{tiles['min_zoom']}-z{tiles['max_zoom']} "
        f"-> {tiles['path']} ({Path(tiles['path']).stat().st_size:,} bytes)"
    )

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
