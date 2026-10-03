"""NC High Peaks Trail Association: points of interest, nothing published (coverage audit 2026-10-01,
batch p09_persist).

The POIs belong to `usfs/` (loaded) and `nc-dpr/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/interactivemaps/maps.htm` loads `TrailSunday3.xml` (lines only), two NWS radar KMLs (`Radar.kml`, "
        "`NWSRadarAnimationofNCRforGSPComposite.kml`), exports of NWS's `watchWarn` MapServer, and three "
        'arcgis.com item ids. `99cd5fbd98934028802b4f797c4b1732` is Esri\'s "USA Topo Maps". `73ed4be5…` and '
        '`f2498e3d…` answer "Item does not exist or is inaccessible". `/interactivemaps/` (the directory) '
        'answers 403. Tried: (1) the club runs no ArcGIS host. (2) AGOL "High Peaks Trail Association" 0, '
        '"Black Mountain Crest" 0, `owner:nchighpeaks` 0. Hub "Mount Mitchell" 63 and "Black Mountains North '
        'Carolina" …',
    ),
    where=(
        "https://arcgis.com",
        "https://nchighpeaks.org/",
    ),
)
