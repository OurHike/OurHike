"""Susquehanna Appalachian Trail Club: trail lines, drawn from another folder's resource (coverage
audit 2026-10-01, batch c2_at_clubs_mid).

The Darlington Trail is not in ATC's `side_trails`: a name search returns only "Darlington Shelter
Side Trail" and "…Water Source Side Trail" (Measured). ~~Whether PASDA's `pasda_dcnr_trails` carries
it is Unvalidated~~ Skeptic, 2026-10-01: settled. `pasda_dcnr_trails` (MapServer/5) has one feature
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "via atc `centerline` for the A.T. Own geometry: two PDF maps on `/satc-maps.html`: "
        "`uploads/1/2/1/5/121538204/satc_11x17.pdf` (2.6 MB, A.T. section + side trails) and "
        "`darlington_11x17.pdf` (1.7 MB)",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://satc-hike.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
