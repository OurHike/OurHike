"""Connecticut DEEP: closures, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

These are static flags, not a notice feed. Where else DEEP announces park closures was not checked,
because the search budget ran out. That gap belongs in the folder's dated note.; Skeptic,
2026-10-01: checked, and the gap closes. DEEP State Parks runs a second site, `https://ctparks.com`
(Drupal) …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`DEEP_Property_Access_Locations` `STATUS`: Open 384 / Closed 1 (Kettletown State Park). "
        '`DEEP_Trails_Set/3` `TRAILSTAT` "Needs Repair": 3. The page '
        "`https://portal.ct.gov/deep/state-parks/emergency-message---parks` was read and held no notice on "
        "2026-10-01. The State Parks hub's 23 DEEP links include no closures page.",
    ),
    where=(
        "https://portal.ct.gov/deep/state-parks/emergency-message---parks",
        "https://ctparks.com",
        "https://ctparks.com/media/2133/download?inline",
        "https://ctparks.com/sitemap.xml",
        "https://ctparks.com/hiking",
        "https://portal.ct.gov/deep/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
