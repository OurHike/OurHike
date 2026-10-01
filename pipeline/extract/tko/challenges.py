"""Trailkeepers of Oregon: challenges, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "REST search `challenge` returns no programme. `/oct/` has only a feedback form for finishers.",
        "Skeptic: REST searches for `hike-a-thon`, `hikeathon`, `finisher`, `certificate` and `bingo` return 0."
        " `patch` returns 4 unrelated posts. The 29 page slugs hold no programme page.",
    ),
    where=("https://trailkeepersoforegon.org/",),
)
