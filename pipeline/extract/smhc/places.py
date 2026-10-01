"""Smoky Mountains Hiking Club: places, published, and not landed (coverage audit 2026-10-01, batch
p02_persist).

Licence: open_licence, public domain, a federal work. data.gov labels GSMNP Trailheads public
domain. Folder: `nps` (GRSM); Fontana Dam in `atc`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`GRSM_TRAILHEADS/FeatureServer/0` has 154 (modified 2025-09-23). `GRSM_PARKING/FeatureServer/0` has "
        "673. `GRSM_MUNICIPAL_BOUNDARIES/FeatureServer/0` has 22 polygons (the gateway towns). "
        "`GRSM_PARK_BOUNDARY/FeatureServer/0` has 19 boundary lines. NPS LRD boundary `UNIT_CODE='GRSM'` has 1 "
        'polygon. Already LOADED via `atc`: `AT_Communities` holds "Fontana Dam"; Gatlinburg, Cherokee, Bryson '
        "City, Robbinsville, Townsend and Cosby are absent. Tried: as for closures.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_TRAILHEADS/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_PARKING/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_MUNICIPAL_BOUNDARIES/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_PARK_BOUNDARY/FeatureServer/0",
        "https://data.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
