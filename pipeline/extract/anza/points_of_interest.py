"""The Anza Trail Foundation: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Expedition campsites are 1775–76 camps, not campgrounds. Must not enter POIs as campsites

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/JUBA__facilities/0`: 372 (Photo 142, Visitor Facility 122+6, Anza NHT Sign 39, Commemorative "
        "Marker 35, Interpretive 26). `JUBA_ExpeditionCampsites`: 87",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://anzatrailfoundation.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
