"""Selma to Montgomery NHT (NPS): points of interest, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Two of the visitor centers are closed today, per alerts

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAPI/visitorcenters` semo 4 (Lowndes, Montgomery, Selma Interpretive Centers; Temporary Selma "
        "Welcome Center). `NPSAPI/campgrounds` semo 3 (Paul Grist State Park, Prairie Creek, Gunter Hill), with"
        " lat/long",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/semo/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
