"""Old Spanish Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: an "interactive map highlighting museums, interpretive centers, and historic sites" plus state '
        "pages (`oldspanishtrail.org/utah/`, `/california/`; search index). Upstream: `NPSAPI/places` olsp ≥23",
    ),
    where=(
        "https://oldspanishtrail.org/utah/",
        "https://oldspanishtrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
