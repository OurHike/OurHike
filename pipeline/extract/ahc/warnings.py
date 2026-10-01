"""Allentown Hiking Club: warnings, drawn from another folder's resource (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

A newsletter article is not a notice.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'via atc `atc_trail_updates`: "Pennsylvania: George W. Outerbridge Shelter Yearly Bear Warning" '
        "(1260.3, 2026-04-30). Club side: one newsletter PDF article (Happy Hiker 2024/10/01, hunting-season "
        "safety)",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://allentownhikingclub.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
