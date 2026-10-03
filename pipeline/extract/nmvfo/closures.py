"""New Mexico Volunteers for the Outdoors: closures, refused by CalTopo's robots.txt (decision 53, phase B,
2026-10-03).

The one closure NMVFO's CalTopo map carried on 2026-10-01 sits on the same `/api/` path
nmvfo/warnings.py records as disallowed, so it is not fetched either. That closure is the Cuba
Ranger District's own, so the Santa Fe National Forest's alerts, which usfs/'s readers take, are the
place it should arrive from; a dbt test should check one against the other once both land.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "caltopo.com/robots.txt, read 2026-10-03: `User-agent: *` / `Disallow: /api/`, which covers the map's "
        "data URL `/api/v1/map/HHBSV6V/since/0`; not requested.",
        "(coverage audit, 2026-10-01) The same CalTopo map. One of 29 scouting reports carries a closure: Los "
        'Pinos Trail FT 46, scouted 9/2/2026: "Because Cuba RD has closed the TH…"',
    ),
    where=(
        "https://caltopo.com/robots.txt",
        "https://coageo.cabq.gov/cabqgeo/rest/services",
        "https://nmvfo.org/",
    ),
    terms="caltopo.com/robots.txt (read 2026-10-03): `User-agent: *` / `Disallow: /api/`",
    reason="refused: robots.txt disallows the only machine-readable path for every agent; held until NMVFO or CalTopo permits",
)
