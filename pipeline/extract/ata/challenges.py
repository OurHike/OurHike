"""Arizona Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Page. Do not load the finishers list (names). Skeptic spot-check: the page returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://aztrail.org/the-trail/completion-award/`: the completion survey, then a finishers list, "
        "sticker and copper belt buckle.",
    ),
    where=("https://aztrail.org/the-trail/completion-award/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
