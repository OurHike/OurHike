"""Laurel Highlands Hiking Trail (PA DCNR): photos, could not be told (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Still UNKNOWN. A Flickr account's per-photo licence was not read.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "DCNR's ArcGIS org has `MustSeeParkPics`, `FallFoliagePics` and `OGF_Pics` feature services, and park "
        "records carry `FLICKR_LINK`. No licence stated on the items I listed.",
        "Skeptic: the `FLICKR_LINK` field is on `Parks/StateParkAmenitiesMASTER/MapServer/0` (126 parks). The "
        'buildings service\'s metadata mentions "links to photos tables for buildings and trails", which are '
        "asset photos. No licence was found on either.",
    ),
    where=(
        "https://gis.dcnr.pa.gov/dcnrbsc/rest/services",
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://dcnr.pa.gov/",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
