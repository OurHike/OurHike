"""El Camino Real de los Tejas NHT Association: warnings, drawn from nps/warnings.py's NPS alerts
resource (decision 53, phase B, 2026-10-03).

NPS's alerts for park code `elte` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.

The club's own site holds no notice: the decision 53 inventory (batch 3, 2026-10-03) read
https://www.elcaminorealdelostejas.org/, and the homepage has no closure or alert channel. So
nothing of the club's own is wired here (phase B, pages, feeds and WordPress, 2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "NPS alerts API, `parkCode=elte` (the decision 53 inventory, batch 3, 2026-10-03): 0 alerts. Allowed zero: total=0 for elte. Landed by nps/warnings.py as nps_alerts.",
        "(coverage audit, 2026-10-01) Same",
        "(the decision 53 inventory, batch 3, 2026-10-03) https://www.elcaminorealdelostejas.org/: the homepage has no closure or alert channel.",
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=elte",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://elcaminorealdelostejas.org/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
