"""Washington Trails Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Skeptic: a search restricted to wta.org finds only "Outdoor Podcasts to Inspire"
(`/news/magazine/features/outdoor-podcasts-to-inspire`), which recommends other people's shows.
Verdict stands. I sent no extra requests to WTA (`Crawl-delay: 60`). (R)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Nav read. A web search found none.",),
    where=(
        "https://wta.org",
        "https://wta.org/",
    ),
)
