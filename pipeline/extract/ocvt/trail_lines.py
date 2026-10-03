"""Outdoor Club at Virginia Tech: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c3_at_clubs_south).

2009 tracks are superseded by ATC's centerline (edited 2026-08-04). Worth keeping only as a dated
cross-check.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`centerline` (16 features, 26.9 mi under `OCVT`) and `side_trails` (7). OCVT's own geometry: 2 GPX "
        "tracks linked from `/about/trailmaint`: `https://ocvt.club/media/gpx/PineSwampto460.gpx` (227,994 "
        "bytes) and `https://ocvt.club/media/gpx/611toI77.gpx` (99,426 bytes). Both are GPSBabel output with "
        "`<time>2009-08-25</time>`, and `ele` is 0.0 throughout.",
    ),
    where=(
        "https://ocvt.club/media/gpx/PineSwampto460.gpx",
        "https://ocvt.club/media/gpx/611toI77.gpx",
        "https://outdoor.org.vt.edu/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
