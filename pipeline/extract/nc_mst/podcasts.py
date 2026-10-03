"""NC Mountains-to-Sea Trail (state-published layer): podcasts, nothing published (coverage audit
2026-10-01, batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Sitemap (733 URLs) and homepage: 0 matches for "podcast".',
        "Skeptic adds: the sitemap is incomplete (see the correction above), so that half is weak. Apple "
        'Podcasts searches for "North Carolina State Parks" and "NC State Parks" (11 shows) found none '
        "published by DPR.",
    ),
    where=(
        "https://services.nconemap.gov/secure/rest/services",
        "https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",
        "https://trails.nc.gov/",
    ),
)
