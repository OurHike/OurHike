"""Potomac Appalachian Trail Club: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `patc_lands_compilation`: PATC Lands Compilation (v1.0.0), 55 polygon features; no places kind.

SAME_AS below: copies of a registered layer, noted and never loaded (decision 34).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("patc_lands_compilation",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
SAME_AS = (
    SameAs(
        original="nps_park_boundaries",
        copy=(
            "https://services7.arcgis.com/BbnVmymrKxjFL0SO/arcgis/rest/services/ShenandoahNP_Boundary_PATC_022023/FeatureServer/0",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "ShenandoahNP_Boundary_PATC_022023: 4 polygons carrying the NPS park-polygon coverage's own columns "
            "(PKPLYNW_, PKPLYNW_ID, ACREAGE), a copy PATC posted in February 2023 of the Shenandoah boundary "
            "nps_park_boundaries carries as unit SHEN (read 2026-10-03)",
            "The coverage audit, batch c2_at_clubs_mid: 'NPS is the authority for this one'",
        ),
    ),
)
