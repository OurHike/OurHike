"""Nez Perce (Nee-Me-Poo) Trail Foundation: places, published, and not landed (coverage audit
2026-10-01, batch p02_persist).

Licence: NPS LRD: open_licence, public domain, a federal work (`copyrightText` "National Park
Service Land Resources Division"). BLM: open_licence: "None, these data are considered public
domain." USFS R01: open_licence, a federal work, with a disclaimer: "The USDA Forest Service makes
no claims …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NPS LRD boundary "
        "`https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2`:"
        " `UNIT_CODE='NEPE'` has 1 (multipart) polygon. NPS Data API `places?parkCode=nepe`: ≥16 places per "
        "audit c11 (today's call hit `OVER_RATE_LIMIT`). USFS KML \"Auto Tour Stops\" (110) is the trail's own "
        "site directory. USFS Region 1 centerline "
        "`…/R01_NezPerceNeeMePoo_NationalHistoricTrail_Centerline/FeatureServer/0` has 532 features, modified "
        "2024-09-28. It is a trail line, noted for the `trail_lines` row that audit c11 already marked …",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
