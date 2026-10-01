"""Colorado Fourteeners Initiative: closures, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

Do not load the peak pages as live closures. The Bross notice predates the 2023 Conservation Fund
purchase described on the projects page. (Skeptic spot-check, 2026-10-01:
`/peaks/mosquito-range/mount-bross/` still opens "Access Update: Summer 2012 … the summit of Mt.
Bross is still closed". The …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Each peak page has an "Important Access Issues" section. Bross: "Access Update: Summer 2012 … the '
        'summit of Mt. Bross is still closed". Bierstadt: Guanella Pass road construction "through October '
        '2015". The sitemap `lastmod` years for the 53 peak pages are 2012: 26, 2013: 20, 2016: 5, 2017: 2, '
        "none later. The only current item: the 2026 preview at `/what-we-do/current-future-projects/` says "
        '"construction projects may limit access to the Kite Lake trailhead in 2026".',
    ),
    where=("https://14ers.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
