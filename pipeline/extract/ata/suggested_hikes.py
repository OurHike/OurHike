"""Arizona Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

The passage pages are open. The Guide is gated. Skeptic spot-check: the passage-1 page returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "43 passage pages, e.g. `/explore/passages/passage-1-huachuca-mountains/`, each with a PDF map, a "
        "history PDF and 3 GPX files. The Day Hiker's Guide (89 day hikes) is a members-only download.",
    ),
    where=("https://aztrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
