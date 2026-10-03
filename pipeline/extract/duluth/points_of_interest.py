"""City of Duluth Open Data: points of interest, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`TrailheadService/MapServer/0`: 131 trailheads with `Trailhead`, `Parking`; item modified 2020-02-20.",),
    where=("https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
