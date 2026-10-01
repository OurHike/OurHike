"""Great Western Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
p01_persist).

Licence: ASP none_stated, with OSM-derived rows under ODbL (Reasoned, see POI). USFS public domain.
Folder: the ASP source; `usfs/` for boundaries.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same `GWT_Points_Public_View/0`: a `Town` field with 65 distinct towns, and service POIs (Food "
        "489, Fuel 133, Lodging 26, Healthcare 21) keyed to them. Staging Area 62 points serve as trailheads.; "
        "Unit boundaries: USFS EDW `EDW_ForestSystemBoundaries_01` and `EDW_ProclaimedForestBoundaries_01` are "
        "listed in EDW. They are not registered, and I did not count them for the GWT.; Tried: 1–7 above.",
    ),
    where=(
        "https://apps.fs.usda.gov/fsgisx02/rest/services",
        "https://services2.arcgis.com/gdcQ6sUWKP8qwBmV/arcgis/rest/services",
        "https://americantrails.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
