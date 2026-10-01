"""Natchez Trace NST (NPS-administered): closures, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

API plus page. The road closures are parkway (driving) closures, and most do not close the footpath.
Skeptic spot-check: the alerts API returns 1 `natr` alert, category Park Closure. The status page
still reads "No Current Trail or Campground Closures — Last updated: August 14, 2026".

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'NPS alerts API `natr`: 1 ("Current Park Closures", category Park Closure). That alert points to '
        '`https://www.nps.gov/natr/planyourvisit/road-and-site-status.htm`, which reads "No Current Trail or '
        'Campground Closures — Last updated: August 14, 2026" and lists road closures (e.g. "MP 437-440 - '
        'Closed for Bridge Construction", April 2026–May 2027).',
    ),
    where=("https://www.nps.gov/natr/planyourvisit/road-and-site-status.htm",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
