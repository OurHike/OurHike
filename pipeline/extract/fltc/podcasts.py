"""Finger Lakes Trail Conference: podcasts, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Skeptic re-checked 2026-10-01: "podcast", "audio" and "episode" searches all return `[]`. A web
search finds only third-party shows, e.g. "Running Inside Out" #109 on the FLT end-to-end FKT, whose
guest is now FLTC's marketing director. That is not an FLTC feed. `FLT News` is a members' magazine.
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('WP search for "podcast" returned 0.',),
    where=(
        "https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services",
        "https://fingerlakestrail.org/",
    ),
)
