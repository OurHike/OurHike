"""Bartram Trail Conference: podcasts, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Neither org has a show on Apple. Third party: "Bartram Trail files" (a named individual, 1 episode, '
        '2020); FKT Podcast "a named individual: Bartram Trail FKT" (2026-09-11). The BTC has a YouTube page '
        "(video).",
        'Skeptic: WP search for "podcast" on BRBTC matches only an event ("Four Ways of Listening to a Forest '
        'with a named individual"). The Apple directory searched by "Bartram Trail" has only "Bartram Trail '
        'files".',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services",
        "https://services1.arcgis.com/gGHDlz6USftL5Pau/ArcGIS/rest/services",
        "https://bartramtrail.org/",
    ),
)
