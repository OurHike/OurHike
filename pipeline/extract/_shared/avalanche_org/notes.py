"""avalanche.org's forecast map layer: not fetched, because its API asks for permission first (decision 53, phase B).

One upstream serves three clubs' avalanche zones, so if it is ever read it is
read once, here (decision 34): the Utah Avalanche Center's zones for wmc/,
the Chugach National Forest Avalanche Information Center (`CNFAIC`) for
iditarod/ and the Mount Washington Avalanche Center (`MWAC`) for rmc/. The
API's root page asks anyone using it to ask first, so this is a stated
permission requirement, not a refusal of automated access, and the decision
53 inventory read the root page and, for CNFAIC and MWAC, one answer each.
Nothing here fetches it. The maintainer sends the request; avalanche ratings
matter from November.

Each club's own warnings row in not_available.toml keeps its note: their other warnings come from
usfs/ and blm/, which other readers take.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "https://api.avalanche.org/ (the API root, 200 text/html, read by the decision 53 inventory, batches 3 and "
        '4, 2026-10-03): "Please contact avalanche.org / American Avalanche Associate for permission" '
        "('Associate' as written). The host has no robots.txt: /robots.txt answers the same HTML root page.",
        "(the inventory, 2026-10-03) `/v2/public/products/map-layer/CNFAIC`: 4 "
        "zones (Chugach State Park; Seward and Lost Lake; Summit Lake; Turnagain Pass and Girdwood), all "
        "`off_season` true, danger 'no rating'; `/map-layer/MWAC`: 1 zone, Presidential Range, off season. Each "
        "zone: name, center_id, danger, danger_level, travel_advice, warning, start_date, end_date, off_season, "
        "link, and a polygon. Weak ETags, cache-control max-age=10.",
        "(the inventory, 2026-10-03) `/v2/public/products/map-layer` for the Utah Avalanche Center's 9 zones "
        "(wmc) was not fetched (batch 3: 'none until permission').",
    ),
    where=(
        "https://api.avalanche.org/",
        "https://api.avalanche.org/v2/public/products/map-layer",
    ),
    terms='https://api.avalanche.org/ (read 2026-10-03): "Please contact avalanche.org / American Avalanche Associate for permission"',
    reason="permission-gated: the publisher asks to be contacted for permission before use; held until the maintainer's request is answered",
)
