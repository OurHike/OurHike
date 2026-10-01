"""MassGIS (Bureau of Geographic Information): points of interest, published, and not landed (coverage
audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa).

Belongs in `ma_dcr/`. Every point is 13–21 years old, so it needs a staleness label. There is no
water type. Stream crossings are a "can I get across" fact, not a water source.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`AGOL/DCR_Roads_and_Trails_Pts/MapServer/0`: 20,786 points. `TYPE` includes Shelter 59, Vista 240, "
        "Trailhead 563, Parking Area 742, Trail Stream Crossing 4,556, Road Ford 348, Road Bridge 122, "
        "Noteworthy Natural Feature 117, Bench(es) 909 and Trail Sign(s)/Kiosk 1,056. The layer's description "
        'says "Field work was conducted during the years 2005 to 2013".',
    ),
    where=("https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/DCR_Roads_and_Trails_Pts/MapServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
