"""Laurel Highlands Hiking Trail (PA DCNR): trail lines, drawn from another folder's resource (coverage
audit 2026-10-01, batch c9_federal_state_rest).

Same geometry, two hosts. DCNR's own server is the steward's original, so prefer it if the two ever
diverge.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Via `pasda` → `pasda_dcnr_trails` (3 LHHT features). DCNR's own: "
        "`https://gis.dcnr.pa.gov/dcnrbsc/rest/services/StateParks/BSP_StateParksTrails/FeatureServer/0`, 1,961"
        " segments, of which 3 are LHHT totalling 67.85 mi (Laurel Ridge State Park), with a `TrailDescription`"
        " field. Explore PA Trails (`www.gis.dcnr.pa.gov/agsprod/rest/services/BRC/EPAT_NEW/MapServer/1`): 684,"
        " the same count as the PASDA layer.",
    ),
    where=(
        "https://gis.dcnr.pa.gov/dcnrbsc/rest/services/StateParks/BSP_StateParksTrails/FeatureServer/0",
        "https://www.gis.dcnr.pa.gov/agsprod/rest/services/BRC/EPAT_NEW/MapServer/1",
    ),
    reason="drawn from pasda/'s resources, extracted once there (decision 34); checked names the layer this org's data"
    " arrives in",
)
