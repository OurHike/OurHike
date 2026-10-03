"""Carolina Mountain Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c3_at_clubs_south).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`centerline` (119 features, 86.2 mi under `CMC`, plus 7.5 mi under `"27"`) and `side_trails` (71). The'
        " MST arrives via `nc_mst_trail`; the Art Loeb Trail via `usfs_trails` (5 segments named `ART LOEB%`). "
        'CMC\'s own geometry: none published. The GPS tracks CMC leaders made for "100 Favorite Trails" went '
        "into a sold Smokies Life map.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://carolinamountainclub.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
