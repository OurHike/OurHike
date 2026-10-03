"""Friends of the Mountains-to-Sea Trail: places, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "18 segment pages, `/segment/1/` … `/segment/18/`, plus `/the-trail/shuttle-services/`, "
        "`/the-trail/trail-angels/` and `/the-trail/trailhead-kiosks/`.",
    ),
    where=("https://mountainstoseatrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
