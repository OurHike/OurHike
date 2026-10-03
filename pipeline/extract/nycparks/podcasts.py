"""NYC Parks: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

Dormant for three years and of no hiker value. Recorded so the next pass does not re-find it.
Loading it is the maintainer's call.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"NYC Parks Covid Oral History", artist "NYC Parks", feed '
        "`https://nycparksoralhistory.blubrry.net/feed/podcast/`. 10 episodes, 2023-05-16 → 2023-08-08 (iTunes "
        "lookup `id1680243471`).",
    ),
    where=("https://nycparksoralhistory.blubrry.net/feed/podcast/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
