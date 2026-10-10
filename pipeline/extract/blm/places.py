"""Bureau of Land Management: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `blm_national_monuments_ncas`: BLM NLCS National Monuments, National Conservation Areas and Similar
  Designations, 57 polygon features; places kind `park`.
- `blm_wilderness_areas`: BLM NLCS Wilderness Areas, 306 polygon features; places kind `park`.
- `blm_wilderness_study_areas`: BLM NLCS Wilderness Study Areas, 1,120 polygon features; places kind
  `park`.
- `blm_recreation_areas`: BLM National Recreation Areas, 588 polygon features; places kind `park`.
- `blm_recreation_site_polygons`: BLM Recreation Sites (polygons), 3,477 polygon features; places kind
  `park`.
- `blm_public_lands_access_lines`: BLM National Public Lands Access Data (lines), 4,835 polyline
  features; no places kind.

Not read: the Surface Management Agency layer (lands/BLM_Natl_SMA_LimitedScale), which says whose land a
hiker stands on, at national scale.
SAME_AS below: copies of a registered layer, noted and never loaded (decision 34).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "blm_national_monuments_ncas",
    "blm_wilderness_areas",
    "blm_wilderness_study_areas",
    "blm_recreation_areas",
    "blm_recreation_site_polygons",
    "blm_public_lands_access_lines",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
SAME_AS = (
    SameAs(
        original="blm_recreation_site_polygons",
        copy=("https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recs_poly/MapServer/0",),
        confirmed=date(2026, 10, 3),
        checked=(
            "Layer 0 of the map service whose layer 1 is registered, both named 'Recreation Sites': 3,477 rows on each, "
            "the same 16 columns, and the same 3,477 Original_GlobalID values (read 2026-10-03)",
        ),
    ),
)
