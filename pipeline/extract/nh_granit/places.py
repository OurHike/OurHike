"""NH GRANIT (University of New Hampshire): places, extracted (decision 54, wave 1; live read 2026-10-03
under lib/user_agent.py's USER_AGENT).

- `nh_conservation_lands`: NH Conservation/Public Lands (CL: Management Status), 13,502 polygon
  features; places kind `park`.
- `nh_recreation_areas`: NH Recreation Inventory: Areas, 2,718 polygon features; places kind `park`.

SAME_AS below: copies of a registered layer, noted and never loaded (decision 34).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("nh_conservation_lands", "nh_recreation_areas")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
SAME_AS = (
    SameAs(
        original="nh_conservation_lands",
        copy=("https://nhgeodata.unh.edu/nhgeodata/rest/services/EC/Conservation/MapServer/6",),
        confirmed=date(2026, 10, 3),
        checked=(
            "Layer 6 ('CL: Solid') of the service whose layer 0 ('CL: Management Status') is registered: 13,502 rows on "
            "each by returnCountOnly, and the same 40 columns (read 2026-10-03)",
            "The same data symbolised two ways in one map service, the ETag of both layer documents one body hash ('13d2e905')",
        ),
    ),
)
