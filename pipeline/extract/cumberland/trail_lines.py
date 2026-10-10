"""Cumberland Trail / Tennessee State Parks: the Cumberland Trail's lines, in TDEC's statewide state-park
layers and in the trail's own CTSST layers.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `tdec_state_park_trails_2024`: Tennessee State Park Trails 2024, view only (TDEC). 2,729 lines, keyed on `GlobalID`.
- `tdec_public_trails_view`: TDEC Public Trails, view (TDEC Bureau of Conservation). 917 lines, keyed on `GlobalID`.
- `tdec_public_trails`: TDEC Public Trails, 2025 hosted layer (TDEC). 2,261 lines, keyed on `GlobalID`.
- `ctsst_open_ct_trail_2020`: Cumberland Trail open sections (CTSST). 33 lines, keyed on geometry.
- `ctsst_comp_trails_2020`: Cumberland Trail complementary trails (CTSST). 163 lines, keyed on geometry.
- `ctsst_road_walks_2020`: Cumberland Trail road walks (CTSST). 6 lines, keyed on `Name`.
- `ctsst_overall_route_2023`: Cumberland Trail overall route, 2023 (CTSST). 4 lines, keyed on `Order_`.
- `ctsst_glyph_parkway`: Glyph Parkway (CTSST). 1 line, keyed on the registry key alone.
- `ctsst_duskin_piney_trail`: Duskin-Piney Trail (CTSST). 1 line, keyed on the registry key alone.
- `ctsst_newby_piney_trail`: Newby-Piney Trail (CTSST). 1 line, keyed on the registry key alone.

Three TDEC datasets are registered because each is its own: no GlobalID is shared between
tdec_public_trails (2,261, stale since 2025-07-09), tdec_state_park_trails_2024 (2,729) and
tdec_public_trails_view (917, a second data model), compared 2026-10-03. `TN_State_Parks_Public_Trails`
is a filtered view of the last (SAME_AS below). PUBLIC_CTSST_2020_gdb's other layers are trailheads,
campsites and natural features (points), properties and public lands (polygons), and trail closures and
hazards (layers 8, 14 and 15), which are the closures worker's.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "tdec_state_park_trails_2024",
    "tdec_public_trails_view",
    "tdec_public_trails",
    "ctsst_open_ct_trail_2020",
    "ctsst_comp_trails_2020",
    "ctsst_road_walks_2020",
    "ctsst_overall_route_2023",
    "ctsst_glyph_parkway",
    "ctsst_duskin_piney_trail",
    "ctsst_newby_piney_trail",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="tdec_public_trails_view",
        copy=("https://services5.arcgis.com/bPacKTm9cauMXVfn/arcgis/rest/services/TN_State_Parks_Public_Trails/FeatureServer/0",),
        confirmed=date(2026, 10, 3),
        checked=(
            "A filtered view of the same hosted layer as TDEC_Public_Trails_(view): all 658 of its GlobalIDs "
            "are among that layer's 917, its 11 fields are a subset of the 49, and both read dataLastEditDate"
            " 2026-10-02 (compared 2026-10-03)",
        ),
    ),
)
