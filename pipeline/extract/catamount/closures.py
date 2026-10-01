"""Catamount Trail Association: closures, published, and not landed (coverage audit 2026-10-01, batch
p07_persist).

Licence: USFS pages are federal works. The ANR service's copyrightText is "VTANRGIS", so
none_stated. Folder: `usfs`. The FPR channel needs a non-walled path, or the maintainer's word on
whether to ask.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "USFS: `https://www.fs.usda.gov/r09/gmfl/alerts` (Green Mountain & Finger Lakes NFs), HTML, 42 alerts. "
        'Each carries an Alert Start/End Date and a "Rec Sites Affected" list. Example: "Heavily damaged or '
        'closed trails" (2025-05-23, last updated 2026-04-24) affects "Abbey Pond Trail, Widow\'s Clearing '
        'Trail, Caywood Point, Moosalamoo Area Trails". "Catamount" appears 0 times on the page today. The '
        "loaded `usfs_trails` has 32 Catamount segments, 27.36 mi, under GMNF admin orgs 092001, 092002 and "
        "092005.; VT ANR: …",
    ),
    where=(
        "https://www.fs.usda.gov/r09/gmfl/alerts",
        "https://anrmaps.vermont.gov/arcgis/rest/services/map_services/MAP_ANR_ANRATLASFPR_WM_NOCACHE/MapServer/3",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
