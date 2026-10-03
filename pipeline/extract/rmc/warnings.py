"""Randolph Mountain Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
p05_persist).

none_stated on the API: no licence field or header, and `avalanche.org/terms-of-use/` and `/terms/`
404 (@unvalidated). The MWAC site says "All Content © 2017 – 2026 Mount Washington Avalanche
Center", which is about its pages. Folder `_shared/avalanche/`, because every US centre is in the
same …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://api.avalanche.org/v2/public/products/map-layer/MWAC`: 1 feature, "Presidential Range", with '
        "fields `danger`, `danger_level`, `travel_advice`, `start_date`, `end_date`, `off_season` and `link`. I"
        " tested 5 points against the polygon. King Ravine floor and the Adams and Madison summits are inside; "
        "Appalachia trailhead and Randolph village are outside. Today `off_season` is true and `danger_level` "
        'is -1 ("no rating"). MWAC\'s footer reads "Mount Washington Avalanche Center USFS Androscoggin Ranger '
        'District 300 Glen Road Gorham NH". The WMNF alerts page carries Caution and Critical keys …',
    ),
    where=(
        "https://api.avalanche.org/v2/public/products/map-layer/MWAC",
        "https://avalanche.org/terms-of-use/",
        "https://randolphmountainclub.org/",
        "https://avalanche.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
