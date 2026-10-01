"""US Fish & Wildlife Service: places, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`.../National_Wildlife_Refuge_System_Boundaries/FeatureServer/0` ("FWS National Realty Boundaries", '
        "owner `an email address`): 1,085 polygons. Also `FWSApproved_Authoritative` and `FWSWilderness`.",
    ),
    where=(
        "https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services",
        "https://fws.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
