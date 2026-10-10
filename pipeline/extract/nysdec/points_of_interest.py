"""DEC's six per-type point services and the back-country asset inventory, loaded whole.

PUBLICUSE 'N' rows load too: public use is a publication rule, and belongs to
dbt. The inventory holds 21,476 points (ORG_COVERAGE_SURVEY.md, batch
b3_nys_dec), of which only privies ship today, through a value allowlist.

Change check: the on-prem statistics fingerprint, count and max(OBJECTID) and
max(UPDATED) in one query, because max(UPDATED) alone cannot see a deleted
lean-to (ELT.md, "The skip-unchanged check, by platform").
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "dec_lean_tos",
    "dec_primitive_campsites",
    "dec_scenic_vistas",
    "dec_firetowers",
    "dec_viewing_areas",
    "dec_parking_areas",
    "dec_backcountry_features",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="dec_backcountry_features",
        copy=("https://services6.arcgis.com/DZHaqZm9cxOD4CWM/arcgis/rest/services/DEC_pointsinterest/FeatureServer/0",),
        confirmed=date(2026, 10, 1),
        checked=(
            "an older export of DEC's own asset points: 4,317 points, last edited 2025-10-14 (read 2026-10-01), "
            "against 4,463 across the six per-type services today, which are DEC's PUBLICUSE='Y' slices of the "
            "back-country inventory (POI_COVERAGE_SURVEY.md, section 2)",
        ),
    ),
)
