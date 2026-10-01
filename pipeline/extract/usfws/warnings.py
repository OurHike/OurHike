"""US Fish & Wildlife Service: warnings, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Hunting season is in scope for warnings. The polygons carry no season dates, so they say where
hunting happens, not when. The dates live in the alert blocks above.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`.../FWS_NWRS_HQ_PublicHuntUnits_view/FeatureServer/0`, "FWS National Hunt Units 2026-2027": 2,215 '
        "polygons, with `Huntable`, `Permit_Required`, `Hunting_Website`. `.../FWS_NWRS_HQ_HuntFishCentroids`: "
        "606 points. Skeptic spot check: still 2,215.",
        "Skeptic adds: `.../Refuge_Lands_Closed_To_Hunting/FeatureServer/0`, 979 polygons for one refuge (Edwin"
        " B. Forsythe), last edited 2021-07-09. It is local and stale, and is recorded so nobody mistakes it "
        "for a national layer.",
    ),
    where=(
        "https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services",
        "https://fws.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
