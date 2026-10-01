"""York Hiking Club: trail lines, drawn from another folder's resource (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

`trail_orgs.json` has no org row for the Mason-Dixon Trail System (grep, Measured). Skeptic
correction, 2026-10-01: the trail itself is not uncatalogued. The `pasda` row's `why` counts
"Mason-Dixon (2)", and `pasda_dcnr_trails` has `NAME01 = 'Mason Dixon Trail'`, `MILES` 188.3,
`UPDATE_` …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("via atc `centerline`. Own geometry: none",),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://yorkhikingclub.com/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
