"""Texas Trail Tamers: trail lines, published, and not landed (coverage audit 2026-10-01, batch
p05_persist).

explicit_restriction. Item `876c319bff684aa4ac92e9e3e7fc3b8c` licenseInfo ends: "This data is not
intended to be used for profit." copyrightText `TPWD|SP|NR|PGR`. The service description warns: "Any
trails may be closed or re-routed without warning." Folder `tpwd/`; GUMO is `nps/`; Violet Crown is
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://tpwd.texas.gov/arcgis/rest/services/Parks/TexasStateParksTrails/MapServer/0` (MapServer, "
        'polyline). McKinney Falls: 56 segments, 12.75 mi, including "Onion Creek Hike and Bike Trail" (10 '
        'segments, 2.98 mi; the 2022–2023 reroute), "Flint Rock Loop Trail" (3, 1.47 mi) and "Homestead Trail" '
        '(11, 3.12 mi). Davis Mountains: 36, 18.36 mi, including "Old CCC Trail", the October 2026 project. '
        "Inks Lake: 40, 9.47 mi. Guadalupe Mountains is LOADED via `nps_trails` (`UNITCODE='GUMO'`: 55). Violet"
        " Crown: Austin PARD `pard_trails_nrpa/FeatureServer/0` has 37 features; River Place has 0. Tried: 1 …",
    ),
    where=(
        "https://tpwd.texas.gov/arcgis/rest/services/Parks/TexasStateParksTrails/MapServer/0",
        "https://texastrailtamers.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
