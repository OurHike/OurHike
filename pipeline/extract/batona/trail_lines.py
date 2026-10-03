"""Batona Hiking Club: trail lines, drawn from another folder's resource (coverage audit 2026-10-01,
batch c1_at_clubs_north).

The Horse-Shoe Trail is not loaded, but it belongs to its own steward, not to Batona.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Club polygon "Batona Hiking Club". The Batona Trail is LOADED via `njdep_park_trails` (21 features '
        "matching `UPPER(TRAIL_NAME) LIKE '%BATONA%'`) and `nj_statewide_trails` (7). The Horse-Shoe Trail "
        "matches 0 features in `pasda_dcnr_trails` (`NAME01`).",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://batonahikingclub.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
