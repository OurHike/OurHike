"""The Trustees of Reservations: points of interest, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Page only, 132 pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Place pages give parking via Google Maps coordinates, e.g. Notchview `@42.5028833,-73.0324264`, and a "
        '"Facilities & Accessibility" section. Also `/places-to-go/inns-campgrounds/`.',
    ),
    where=("https://thetrustees.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
