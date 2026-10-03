"""Georgia Appalachian Trail Club: closures, published, and not landed (coverage audit 2026-10-01,
batch b4_oprhp_mohonk_gatc).

GATC publishes reroutes and access-road closures that ATC's reviewed file does not carry. The posts
mix closures with news, so they need the human-review treatment `lib/atc_updates.py` encodes. The
January road closures are probably stale by now (@unvalidated). Skeptic re-check: `/feed/` answers …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'News RSS `https://georgia-atclub.org/feed/` (30 posts, one category). Relevant posts: "Byron Herbert '
        'Reece Trail Reroute" (2026-06-05); "A. T. Access Points Impacted by Winter Storm" (2026-01-29: '
        '"Highway 348/Richard Russell Scenic Highway is impassable", serving Tesnatee and Hogpen Gaps; FS Road '
        '42 to Springer "in very rough shape"); "Winter Storm Damage along the A.T. in Georgia" (2026-01-28); '
        '"Government Shutdown and the A.T." (2025-10-02). The ATC path is LOADED (`atc_trail_updates`), but '
        "`reference/atc_updates.json` (reviewed 2026-08-24) has 3 Georgia rows and 0 closures among them.",
    ),
    where=(
        "https://georgia-atclub.org/feed/",
        "https://georgia-atclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
