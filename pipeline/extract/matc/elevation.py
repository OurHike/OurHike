"""Maine Appalachian Trail Club: elevation, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

USGS 3DEP (`fetch_elevation.py`, `_shared/`) covers it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Nav, `/wp-json/wp/v2/pages` (61 pages listed), ArcGIS search: no elevation product.",),
    where=("https://matc.org/",),
)
