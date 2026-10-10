"""PASDA / PA DCNR: places, extracted (decision 54, wave 1; live read 2026-10-03 under lib/user_agent.py's
USER_AGENT).

- `dcnr_state_park_boundaries`: Pennsylvania State Park Boundaries (DCNR), 125 polygon features; places
  kind `park`.
- `dcnr_state_forest_boundaries`: Pennsylvania State Forests (DCNR Bureau of Forestry), 662 polygon
  features; places kind `park`.
- `pasda_dcnr_wild_natural_areas`: DCNR BOF Wild and Natural Areas 202402 (PASDA), 141 polygon features;
  places kind `park`.
- `pasda_dcnr_local_parks`: DCNR Local Park 202406 (PASDA), 6,325 polygon features; places kind `park`.

SAME_AS below: copies of a registered layer, noted and never loaded (decision 34).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "dcnr_state_park_boundaries",
    "dcnr_state_forest_boundaries",
    "pasda_dcnr_wild_natural_areas",
    "pasda_dcnr_local_parks",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
SAME_AS = (
    SameAs(
        original="dcnr_state_park_boundaries",
        copy=("https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR/MapServer/8",),
        confirmed=date(2026, 10, 3),
        checked=(
            "PASDA's 'DCNR State Parks 202503' (124 polygons) against DCNR's live State Park Boundaries (125), both read "
            "2026-10-03: the same columns (PARK_NAME, GIS_ACRE, ICSORG, NICKNAMES, TYPE, WEBLINK, FILE_NAME) and "
            "copyrightText 'DCNR - Bureau of State Parks' on the copy",
            "114 of the copy's 124 PARK_NAME values are the live layer's with ' State Park' or ' State Recreation Area' "
            "dropped, and the other 10 the same units under a longer type ('Boyd Big Tree' is 'Boyd Big Tree Preserve "
            "Conservation Area'): the March 2025 vintage of the same dataset, one unit behind",
        ),
    ),
    SameAs(
        original="dcnr_state_forest_boundaries",
        copy=("https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR/MapServer/6",),
        confirmed=date(2026, 10, 3),
        checked=(
            "PASDA's 'DCNR BOF State Forests 202503' (670 polygons) against DCNR's live State Forests (662), read "
            "2026-10-03: the Bureau of Forestry's own schema on both (SF_Name, WnaType, WnaName, StParkName, SGL_No, "
            "District, LandManager, Acreage, GlobalID), the copy's column names cut to ten characters by a shapefile",
            "20 SF_Name values on the copy, all 20 among the live layer's 21: the March 2025 vintage of the same dataset",
        ),
    ),
)
