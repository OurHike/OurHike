"""NYC Parks: closures, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

It is mostly facility closures: recreation centres, marinas, playgrounds, and the Tide Gate Bridge
in Flushing Meadows. Its trail yield is low, but it is NYC Parks' only machine-readable closure
channel, and it costs one HTTP GET per day. The `bigapps` index page returns a CloudFront 403 to a …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.nycgovparks.org/bigapps/DPR_ParkClosure_001.json`:",
        "8,069 rows (3,352 not archived), Last-Modified 2026-09-30 08:00 GMT, so regenerated daily.",
        "Fields `start`, `end`, `closure_type`, `message`, `Prop_ID`, `created`, `modified`, `is_archived`. "
        "`Prop_ID` is the same `gispropnum` key `nyc_park_polygons` uses.",
        "30 rows active on 2026-10-01: Closed 14, Partially Closed 2, Open 14.",
        'Only 2 rows ever mention a trail. The newest is "The Pat Dolan Trail will be closed due to '
        'construction from August 3-7, 2026."',
        "Data dictionary at `/bigapps/desc/DPR_ParkClosure_001.txt`.",
    ),
    where=(
        "https://www.nycgovparks.org/bigapps/DPR_ParkClosure_001.json",
        "https://nycgovparks.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
