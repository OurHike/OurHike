"""MassGIS (Bureau of Geographic Information): podcasts, nothing published (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

Skeptic, 2026-10-01, a cross-reference for `ma_dcr/`: DCR does publish one. "Dispatches from the
Parks", `itunes:author` "Massachusetts Department of Conservation and Recreation", feed
`https://feeds.acast.com/public/shows/646688d4022559001174ccdc` (iTunes `1691072197`), copyright
DCR. It holds 1 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('iTunes search "MassGIS" found no show by MassGIS.',),
    where=("https://feeds.acast.com/public/shows/646688d4022559001174ccdc",),
)
