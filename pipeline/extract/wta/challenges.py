"""Washington Trails Association: challenges, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Skeptic: the search index also shows `/news/signpost/get-outside-with-winter-hiking-bingo` and a
2026 Hike-a-Thon BINGO card. Bingo squares are "favorite things about winter hiking or a WTA
resource", not places, and the prize is a drawing entry. Same reasoning as OTA's Hike and Float:
verdict …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/get-involved/join/hike-a-thon` is an August fundraiser (538 hikers in 2025, per a search snippet), "
        "not a place-based programme.",
    ),
    where=("https://wta.org/",),
)
