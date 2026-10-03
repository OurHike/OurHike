"""Colorado Fourteeners Initiative: closures, nothing current published (decision 53 phase B,
2026-10-03).

The decision 53 inventory (batch 4) re-read the coverage audit's two pages. Mount Bross's peak page
(https://www.14ers.org/peaks/mosquito-range/mount-bross/) carries 'Access Update: Summer 2012 … the
summit of Mt. Bross is still closed' (WordPress page 417, modified 2012-05-23), superseded by the
2023 purchase the projects page describes, so it must never load as a live closure. The projects
page's one 2026 line, 'these construction projects may limit access to the trailhead in 2026' (Kite
Lake; https://www.14ers.org/what-we-do/current-future-projects/, page 225, modified 2026-04-01), is
a project note, not a notice. robots.txt allows both; no terms page was found.

Before decision 53 phase B, 2026-10-03, this note read:

Colorado Fourteeners Initiative: closures, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

Do not load the peak pages as live closures. The Bross notice predates the 2023 Conservation Fund
purchase described on the projects page. (Skeptic spot-check, 2026-10-01:
`/peaks/mosquito-range/mount-bross/` still opens "Access Update: Summer 2012 … the summit of Mt.
Bross is still closed". The …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Each peak page has an "Important Access Issues" section.
Bross: "Access Update: Summer 2012 … the summit of Mt. Bross is still closed". Bierstadt: Guanella
Pass road construction "through October 2015". The sitemap `lastmod` years for the 53 peak pages are
2012: 26, 2013: 20, 2016: 5, 2017: 2, none later. The only current item: the 2026 preview at
`/what-we-do/current-future-projects/` says "construction projects may limit access to the Kite Lake
trailhead in 2026".

Its `where`: https://14ers.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(the decision 53 inventory, batch 4, 2026-10-03) https://www.14ers.org/peaks/mosquito-range/mount-bross/: 200, a 2012 access notice (REST pages/417 modified 2012-05-23); https://www.14ers.org/what-we-do/current-future-projects/: 200, one 2026 project sentence (pages/225 modified 2026-04-01). No current closure or alert channel.",
    ),
    where=(
        "https://www.14ers.org/peaks/mosquito-range/mount-bross/",
        "https://www.14ers.org/what-we-do/current-future-projects/",
    ),
    reason="not published: the club's pages hold a 2012 access notice and a projects note, not current notices",
)
