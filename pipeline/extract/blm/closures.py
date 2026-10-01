"""Bureau of Land Management: closures, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Format: RSS of mixed press releases, so it needs decision 7's classifier and a closure-keyword
filter. There is no geometry; a release names a county or area. `/alerts` was empty when the server
sent it (skeptic, Measured). That a Drupal view would have rendered items there is Reasoned.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://www.blm.gov/alerts`: server-rendered list with region filter, read "No Results" today. '
        "Closures appear in the state press-release RSS feeds (13, listed at "
        "`https://www.blm.gov/info/RSS-feeds`). `https://www.blm.gov/press-release/utah/rss`: 51 items, newest "
        '2026-09-30, including "BLM to Temporarily Close Public Lands in Iron County for Special Recreation '
        'Events". Federal Register API, BLM agency, 2026: 0 documents matching "temporary closure". BLM EGIS '
        'AGOL search: 138 hits for closure/restriction/alert terms, no closure-order layer (Colorado "Closed to'
        ' Fluid Mineral Leasing" is …',
    ),
    where=(
        "https://www.blm.gov/alerts",
        "https://www.blm.gov/info/RSS-feeds",
        "https://www.blm.gov/press-release/utah/rss",
        "https://gis.blm.gov/arcgis/rest/services",
        "https://blm.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
