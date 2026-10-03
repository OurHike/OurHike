"""Society for the Protection of NH Forests: podcasts, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

The feed is NHPR's and looks stale against the show. This belongs in `_shared/podcasts`, attributed
to its co-producers. Skeptic correction (M, 2026-10-01): the feed above is a dead copy. The live
feed is the one Apple's directory lists: …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Something Wild", which NHPR introduces as "a joint production of NH Audubon, The Society for the '
        'Protection of New Hampshire Forests & NHPR". RSS: '
        "`https://www.nhpr.org/podcast/something-wild/rss.xml` (20 items with enclosures; newest in the feed is"
        " 2023-03-24; ©2026 NHPR). The SPNHF site has 166 `/something-wild/` transcript pages, the latest dated"
        " 2026-09-17.",
    ),
    where=(
        "https://www.nhpr.org/podcast/something-wild/rss.xml",
        "https://forestsociety.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
