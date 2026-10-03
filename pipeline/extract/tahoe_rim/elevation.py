"""Tahoe Rim Trail Association: elevation, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "All 32 services listed. No elevation product; `Vistas.Vista_Elev` is a single attribute.",
        'Skeptic adds: all 71 org items were scanned, and the only elevation-like one is a "Topographic" layer '
        "package (2021). WebFetch of `tahoerimtrail.org/maps-trail-info/` found segment pages, the web map, "
        "water and conditions pages, and no elevation profile. The per-segment profiles hikers cite are in the "
        "National Geographic map that TRTA sells (`/product/national-geographic-tahoe-rim-trail-map/`), which "
        "is a commercial third-party product, not TRTA's publication.",
    ),
    where=(
        "https://tahoerimtrail.org/maps-trail-info/",
        "https://tahoerimtrail.org/",
        "https://services7.arcgis.com/NchnBpgTjegMVinZ/arcgis/rest/services",
    ),
)
