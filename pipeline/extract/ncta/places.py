"""North Country Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Format page: the Trail Towns pages `northcountrytrail.org/our-work/trail-towns/<town>/` (WordPress "
        "search returned Cohasset & Grand Rapids, Abercrombie, Ely, North Creek, Battle Creek and Zoar). "
        "`Michigan_Public_Lands_WFL1` (763 polygons) is a copy of other publishers' land data.",
    ),
    where=(
        "https://northcountrytrail.org/our-work/trail-towns/",
        "https://northcountrytrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
