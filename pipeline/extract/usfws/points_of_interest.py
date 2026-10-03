"""US Fish & Wildlife Service: points of interest, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

`Public_Use`, `Public_View` and `Status` (`Valid` / `Needs Validation` / `Delete`) have to filter
it. The layer also holds sewage plants and fuel tanks. No water-source points were found for hikers:
`FWS_Assets_Water_Resources_Inventory_PublicView` is water-management infrastructure and was not …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../FWS_HQ_Fac_Property_Pt_PublicView/FeatureServer/0`: 14,921 points. `Prop_Type` has 67 codes, "
        "including Campground, Campsite, Overlook, Observation Deck / Platform, Parking Lot, Kiosks, Picnic "
        "Area, Pullout. `.../FWS_Access_PublicView/FeatureServer/0`: 1,757 access points, of which 832 have "
        "`Acc_Type='Trailhead'`.",
    ),
    where=(
        "https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services",
        "https://fws.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
