"""NYC Parks: warnings, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

Under decision 7 these rows land in `warnings`, labelled "not reviewed". Trail hours (dusk closing)
are the one hazard-shaped fact here: a hiker in a park after hours.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same feed's `closure_type = 'Open'` rows are notices that close nothing: 578 all-time, 14 active, "
        'for example the Ecology Park habitat notice at `B406`. `Parks Signs` carries trail hours ("Trail With '
        'Hours"). Checked and rejected: Urban Park Ranger Animal Condition Response (see Do not load); `Parks '
        "Inspection Program – Conditions & Hazards` `ibip-ftv5`, which is inspection findings, not public "
        "notices; `DPR_BeachesClosures_001`, which is water quality and is kept out of `warnings` by decision "
        "2.",
    ),
    where=("https://data.cityofnewyork.us/d/ibip-ftv5",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
