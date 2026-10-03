"""Adirondack Mountain Club: podcasts, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Skeptic: a second web search restricted to adk.org (podcast OR listen) returns only a 2018 Summit
Steward report that mentions another group's podcast. adk.org itself was not crawled (terms).
Stands, on search evidence only.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Web search: \"ADK Talks\" is adktaste.com's podcast, not this club's.",),
    where=(
        "https://adktaste.com",
        "https://adk.org",
    ),
)
