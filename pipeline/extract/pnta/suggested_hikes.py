"""Pacific Northwest Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

Page. Skeptic: `/pnta/sections-of-the-pnt/` now 301s to `/pnta/know-before-you-go/` ("Sections of
the PNT" in `llms.txt`). Use the target URL.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`/pnta/sections-of-the-pnt/`: 10 section pages. WP category `day-hikes`: 1 post.",),
    where=("https://pnt.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
