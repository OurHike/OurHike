"""Standing Stone Trail Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Via `pasda` → `pasda_dcnr_trails`: 1 feature, `NAME01='Standing Stone Trail'`, `NAME02='Mid State "
        "Trail'`, `MILES` 75.66, `UPDATE_` 2016-11-17. Own geometry: KML on Facebook (not fetched); Avenza maps"
        ' published in Avenza\'s store under "Mid State Trail Association Inc"; 13 PDF maps (`/pdf-maps`, '
        '"Updated on 4-9-2023").',
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://standingstonetrail.org/",
    ),
    reason="drawn from pasda/'s resources, extracted once there (decision 34); checked names the layer this org's data"
    " arrives in",
)
