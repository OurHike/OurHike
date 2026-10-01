"""Save Mount Diablo: places, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Terms-blocked.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The preserve pages for Curry Canyon Ranch and Mangini Ranch Educational Preserve. A "
        "`protected-properties` custom post type exists in `/wp-json/`, but I did not read its contents once I "
        "had read the terms.",
    ),
    where=("https://savemountdiablo.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
