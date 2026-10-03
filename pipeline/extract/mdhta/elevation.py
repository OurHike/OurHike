"""Maah Daah Hey Trail Association: elevation, carried as Z on the trail GeoJSON files trail_lines.py would load.

The trail guide links 20 GeoJSON files, the Maah Daah Hey and its connectors,
and their vertices are three-dimensional. One vertex read against 3DEP gives
the unit as metres, which is one point, not a measurement of the file
(@unvalidated; a sample along the line against 3DEP settles it, and whether
the Z came from GPS or a DEM). A GeoJSON file is decision 54's wave 2 (the
`gis_file` kind), and the files are trail lines, so trail_lines.py registers
them and this file becomes `SHARES` once that resource exists.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "`/trail-guide/` (read 2026-10-03, robots.txt first): 20 GeoJSON files in `data-geojson` attributes "
        "under `/wp-content/uploads/`, among them `2015/07/mdht-minified-2025-1.geojson`, `long-x-1.geojson` "
        "and `2025/07/white-butte-minified-2025-2.geojson`",
        "HEAD `mdht-minified-2025-1.geojson` 2026-10-03: 114,768 bytes, Last-Modified 2025-07-25",
        "its first vertex is `[-103.4449419, 46.5982664, 774.478]` (coverage audit 2026-10-01); 3DEP through EPQS "
        "reads 775.02 m there (2026-10-03), so that one vertex's Z is in metres",
        "coverage audit (2026-10-01, batch c8_regional_5): `long-x-1` starts at 782.28, and the trail pages "
        "render an `elevation-profile-holder`",
    ),
    where=(
        "https://mdhta.com/trail-guide/",
        "https://mdhta.com/wp-content/uploads/2015/07/mdht-minified-2025-1.geojson",
        "https://mdhta.com/",
    ),
    reason="carried on a trail GeoJSON, a GIS file for decision 54's wave 2: becomes SHARES once trail_lines.py loads it",
)
