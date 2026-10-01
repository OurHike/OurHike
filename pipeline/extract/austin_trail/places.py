"""The Trail Foundation (Austin): places, published, and not landed (coverage audit 2026-10-01, batch
p08_persist).

Licence, TTC management areas: "…represents only the approximate relative location of property
boundaries. This product has been produced by The Trail Conservancy for the sole purpose of
geographic reference. No warranty is made by The Trail Conservancy regarding specific accuracy or
completeness." …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "TTC `TTC_Management_Areas_AID/FeatureServer/0`: 269 polygons, edited 2026-09-26, with 27 distinct "
        "`LOCATION_NAME` values: Auditorium Shores, Holly Shores, Peace Point, Vic Mathias Shores, Shoal Creek "
        "Greenbelt, Johnson Creek Greenbelt, Lady Bird Lake, Roy G. Guerrero Colorado River Metro Park and "
        'others. Also TTC: `Parks` 303 polygons (PARD schema, 2020) and `2026_TTC_Planned` layer 12 "TTF Park '
        'Area" 78 (edited 2026-10-01). City: Socrata `BOUNDARIES_city_of_austin_parks` (`v8hw-gz65`, owner '
        '"Austin Parks and Recreation Owners", rows updated 2026-09-27): 370 rows. Tried: 1, 2, 3 (the City …',
    ),
    where=("https://services7.arcgis.com/X8BO7jvq5nMMymtB/arcgis/rest/services/TTC_Management_Areas_AID/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
