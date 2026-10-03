"""Texas Trail Tamers: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Same nav.",
        "Skeptic: the homepage HTML (60,383 bytes; the nav is drawn by script) has 3 static internal links: "
        "`/join-us`, `/opensearch.ashx`, and a training deck, `/resources/Documents/Central Texas Trail Tamers "
        "Intro to Trails.pptx`. Its text has no hike, condition, challenge or podcast wording.",
    ),
    where=("https://texastrailtamers.org/",),
)
