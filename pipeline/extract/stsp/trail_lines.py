"""Star-Spangled Banner NHT (NPS): trail lines, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Land and water route. Chesapeake Conservancy also has a MapJournal

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/Sta_Spangled_Banner_National_Historic_Trail_Official_Centerline/0`: 1 line (2018-06-01). `nps_trails` STSP: 0",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/stsp/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
