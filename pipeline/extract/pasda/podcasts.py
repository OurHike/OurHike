"""PASDA / PA DCNR: podcasts, nothing published (coverage audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa).

Skeptic, 2026-10-01: kept, after ruling out a near miss. iTunes "DCNR" ranks first "Hemlocks to
Hellbenders" (`https://rss.buzzsprout.com/2110005.rss`, 96 items, newest 2026-09-30, "highlighting
Pennsylvania's parks, forests and great outdoors"), whose episodes speak of DCNR as "we". But its
site …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'iTunes search "Pennsylvania DCNR": the nearest show is "Think Outside with the Pennsylvania Parks and '
        "Forests Foundation\" (artist a named individual, 43 episodes, newest 2026-09-23), which is PPFF's, not "
        "DCNR's. That matches c9.",
    ),
    where=("https://rss.buzzsprout.com/2110005.rss",),
)
