"""Bartram Trail Conference: challenges, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No completion or patch programme in BRBTC's nav, FAQs or sitemaps. The BTC's \"Fothergill Award\" is a scholarly award.",
        'Skeptic, verdict upheld: WP search for "challenge", "thru" and "patch" is empty. None of the 9 FAQ '
        "slugs is about completion. None of the 72 event slugs is a challenge (the closest is "
        '"2026-spring-sweep").',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/ArcGIS/rest/services",
        "https://bartramtrail.org/",
    ),
)
