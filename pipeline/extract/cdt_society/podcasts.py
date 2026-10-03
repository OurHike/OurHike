"""Continental Divide Trail Society: podcasts, could not be told (coverage audit 2026-10-01, batch
c10_nst_rest).

Still UNKNOWN. A directory search cannot prove a site never linked audio.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Site unreachable.",
        'Skeptic: the iTunes podcast directory search for "Continental Divide Trail Society" returns one '
        "unrelated show (Dixie LIVE on the Continental Divide Trail, 33 episodes, last 2018-10-04, by its "
        "hosts).",
    ),
    where=("https://cdtsociety.org/",),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
