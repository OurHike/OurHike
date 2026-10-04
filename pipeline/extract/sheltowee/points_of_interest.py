"""Sheltowee Trace Association: points of interest, published with no coordinate of its own, and not landed
(decision 54, wave 5, read live 2026-10-04).

The campgrounds page lists the trail's campgrounds with FarOut mileages, seasons and fees, and each links a
Google Maps short link (32 such links on the page) rather than stating a fix. A short link resolves to
Google's place for a name, which is a lookup, not the association's coordinate, so it is not followed. The
"Major Trailheads and Road Crossings" PDF gives mileposts and overnight-parking rules with no coordinate (the
coverage audit, 2026-10-01). Needs a per-site reader, not built in this pull request, with a fix for each site
that a person reviews.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (Squarespace's: `User-agent: *` disallows /config, /search, /api/, /static/ and query-string "
        "views; named AI crawlers, not ours, are refused), then /campgrounds, read 2026-10-04 under "
        "lib/user_agent.py's agent: 200, 627,042 bytes, 32 Google Maps links, no coordinate in the page.",
        "the coverage audit (2026-10-01, batch c8_regional_5): 16 campgrounds; `/s/major_trailheads.pdf`, 1 page, "
        "2020-02-17, mileposts and overnight-parking rules, no coordinates; 'Google Maps Points of Access' "
        "(goo.gl/maps/eqnPDxPa3ZqnranP8), a Google map, not opened.",
    ),
    where=("https://sheltoweetrace.org/campgrounds", "https://sheltoweetrace.org/s/major_trailheads.pdf"),
    reason="needs a per-site reader, not built in this pull request: the campgrounds link Google places and state no fix",
)
