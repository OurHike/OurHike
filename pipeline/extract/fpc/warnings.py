"""Forest Park Conservancy: warnings, published, and not landed (coverage audit 2026-10-01, batch
p07_persist).

As for closures.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same page has 3 "Caution" entries, e.g. "Wildwood Trail at mile 15.2 - Caution: There is a stepped'
        ' bypass route to the bridge… Please use caution at this temporary crossing". Tried: as for closures.',
    ),
    where=(
        "https://www.portlandmaps.com/od/rest/services",
        "https://forestparkconservancy.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
