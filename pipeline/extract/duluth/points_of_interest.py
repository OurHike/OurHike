"""City of Duluth: points of interest, not found where the coverage audit read them.

The audit read a TrailheadService/MapServer/0 of 131 trailheads (item modified 2020-02-20). The utility proxy
that serves Duluth's registered trail line lists one service under Parks, TrailsDuluthService, and no
trailhead service, on 2026-10-03.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "the utility proxy's services root and its Parks folder, read 2026-10-03: Parks/TrailsDuluthService (MapServer) only",
    ),
    where=("https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services",),
    reason="not found on 2026-10-03 where the coverage audit read it; checked says where this read looked",
)
