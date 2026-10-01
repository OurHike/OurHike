"""NJDEP / NJGIN — Statewide Trails: podcasts, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

Dormant for 8 years. Low value.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Discover DEP: the Official Podcast of the NJ Department of Environmental Protection", feed '
        "`https://feed.podbean.com/njdep/feed.xml` (200, 392,517 bytes). 95 episodes, 2016-04-21 → 2018-05-01. "
        "12 titles mention trail, park, hike, bear, fire or forest (iTunes `id1109394162`).",
    ),
    where=("https://feed.podbean.com/njdep/feed.xml",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
