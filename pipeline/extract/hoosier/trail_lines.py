"""Hoosier Hikers Council: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

No sources.json row mentions Indiana. IN DNR is a candidate for a new state-clearinghouse catalogue
row, with `hoosier` reading through it as `via` or as a dual source (#1709 — Register the steward
and the redistributor both, and declare which one wins where they overlap).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own: `https://www.hoosierhikerscouncil.org/assets/2023_TecumsehTrailTrack.gpx` (GPX, 817,229 bytes, "
        'Last-Modified 2024-03-12). Upstream: IN DNR "Indiana Trails Inventory Open Trails" '
        "`https://gisdata.in.gov/server/rest/services/Hosted/Trails_AGOL_RO/FeatureServer/0` (ArcGIS layer, "
        "5,496 polylines, maxRecordCount 1000). In it, `segname LIKE '%KNOBSTONE%'` returns 4 rows and "
        "`'%TECUMSEH%'` returns 6. Item licence text: \"AS-IS … Credit should be given to the Indiana Department"
        ' of Natural Resources".',
    ),
    where=(
        "https://www.hoosierhikerscouncil.org/assets/2023_TecumsehTrailTrack.gpx",
        "https://gisdata.in.gov/server/rest/services/Hosted/Trails_AGOL_RO/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
