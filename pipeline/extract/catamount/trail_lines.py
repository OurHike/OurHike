"""Catamount Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

GeoJSON beats GPX. The CTA's own page says the map and GPX "were last updated in 2021, so some
reroutes will not be available", while section PDFs were updated in 2025. On ArcGIS, the org's own
`catamounttrail` account holds only tile layers, offline map areas and a web map with no operational
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Interactive map data, served as static files:",
        "`https://catamounttrail.org/CTA_TrailMap/data/CTA_MAINTRAIL_MASTER_WEBMAP.geojson` (871,075 B, "
        "last-modified 2023-09-19)",
        "`…/CTA_SIDETRAILS_MASTER_WEBMAP.geojson` (803,294 B, 2017)",
        "`…/CTA_SECTIONS_WEBMAP.geojson` (10,979 B, 2017); Also a GPX+KML zip: "
        "`wp-content/uploads/CT_fullRoute_gpxKML_122022.zip` (479,596 B, 2022-12-20).",
    ),
    where=("https://catamounttrail.org/CTA_TrailMap/data/CTA_MAINTRAIL_MASTER_WEBMAP.geojson",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
