"""Mid State Trail Association (PA): closures, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

A page. The RSS cannot detect edits. Skeptic correction (M, 2026-10-01): the alerts are newer than
"June 16, 2023". Each section page's "Last Updated on" line reads July 01, 2026 for
`/134-section-1`, October 12, 2025 for `/150-section-14` and `/156-section-20`, and June 06, 2024
for …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/index.php/the-trail/section-updates`: 20 section articles plus spurs, e.g. `/148-section-12` with "
        'dated "Alerts" (latest seen June 16, 2023). There are region update pages too. Joomla RSS at '
        "`?format=feed&type=rss` exists, but its `pubDate` is each article's 2012 creation date.",
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://services6.arcgis.com/DtSEkvbAjAfDY35J/arcgis/rest/services",
        "https://hike-mst.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
