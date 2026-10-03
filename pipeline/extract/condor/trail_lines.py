"""Condor Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Not LOADED via `usfs`. The 2 USFS matches are other trails (correction 1). No licence stated. ArcGIS
has only a third-party advocacy layer: `ForestWatchGIS` `CCHPA_Condor_Trail`, 1 polyline drawn for a
legislative map.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "KML, 4 county files at `http://www.condortrail.com/wp-content/uploads/kml/`, all last-modified 2021-07-29:",
        "`CT2020_VenturaCounty.kml`: 765,085 B, 31 LineStrings",
        "`…SantaBarbaraCounty.kml`: 691,851 B, 36 LineStrings",
        "`…SanLuisObispoCounty.kml`: 295,225 B, 26 LineStrings + 2 Polygons",
        "`…MontereyCounty.kml`: 176,578 B, 59 LineStrings; Total: 152 lines.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://condortrail.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
