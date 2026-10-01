"""US Army Corps of Engineers: points of interest, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "RIDB API (`/facilities`, `/campsites`; key) or the bulk export. Tulsa District recreation features: "
        "Trailheads 100, Campgrounds 133, Campsites 6,013, Recreation Features 1,927.",
    ),
    where=("https://usace.army.mil/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
