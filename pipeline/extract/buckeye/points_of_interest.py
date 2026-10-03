"""Buckeye Trail Association: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Restricted. Counts are lines matched by the pattern `^Points? ` (R ±).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "BTA ArcGIS `parking_web_final/FeatureServer/0`: 422 points (`Name`, `type_pking`, `term_pking`, "
        '`access_pki`), last edited 2020-09-19, copyright "Buckeye Trail Association". The 26 section pages '
        'carry "Parking locations" (about 358 point lines), "Camping locations" (about 104 lines, e.g. Whipple '
        'Pt 13 "Halfhill Campsite, primitive, tenting, water needs to be purified") and resupply.',
    ),
    where=("https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services/parking_web_final/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
