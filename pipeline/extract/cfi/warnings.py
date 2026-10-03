"""Colorado Fourteeners Initiative: warnings, nothing current published (decision 53 phase B,
2026-10-03).

The decision 53 inventory (batch 4) re-read the coverage audit's two pages. Mount Bross's peak page
(https://www.14ers.org/peaks/mosquito-range/mount-bross/) carries 'Access Update: Summer 2012 … the
summit of Mt. Bross is still closed' (WordPress page 417, modified 2012-05-23), superseded by the
2023 purchase the projects page describes, so it must never load as a live closure. The projects
page's one 2026 line, 'these construction projects may limit access to the trailhead in 2026' (Kite
Lake; https://www.14ers.org/what-we-do/current-future-projects/, page 225, modified 2026-04-01), is
a project note, not a notice. robots.txt allows both; no terms page was found. The mine-stope and
lightning hazards are static peak-page text: true, and not notices.

Before decision 53 phase B, 2026-10-03, this note read:

Colorado Fourteeners Initiative: warnings, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

These are static hazards, written 2012–2017. The mine-stope hazard is the kind that stays true.
(Skeptic: the Bross page's stope text was confirmed. `/mountain-safety/` (sitemap lastmod
2019-10-23) is three video series: Mountain Safety, Intro to 14er Gear, Understanding Altitude
Illness. That is …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Each peak page has "Peak Specific Environmental and Safety
Concerns": lightning above treeline, and on Lincoln, Democrat and Bross, collapsing mine stopes
"only inches from the surface".

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
