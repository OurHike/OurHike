"""National Park Service: points of interest, published, and not landed (coverage audit 2026-10-01,
batch b6_federal).

Held on scope, not terms (the `nps-poi` row): it needs a corridor clip and a POITYPE allowlist that
a person reads. `max(CREATEDATE)` is `9999-09-09`, a sentinel, so use `EDITDATE` for freshness.
Skeptic: GRSM's layer is a steward-stated capacity for the Smokies' A.T. shelters. Whether the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../NationalDatasets/NPS_Public_POIs/FeatureServer/0` (point): 35,639. `max(EDITDATE)` 2026-09-17. "
        "`POISTATUS` is null on 30,306, Existing 5,205, Planned 87, Temporarily Closed 4. Siblings: "
        "`NPS_Public_ParkingLots` 6,743 polygons, `NPS_Public_Buildings` 29,054 polygons, `NPS_Public_Roads` "
        "31,313 lines. Water and shelter types, from c9: Potable Water 214, Drinking Water 136, Water - "
        "Drinking/Potable 34, Spring 25, Shelter 117, Weather Shelter 29, Backcountry Campsite 203. API "
        "`/campgrounds` 665 (c9).",
        "Skeptic adds (Measured 2026-10-01): (1) The A.T.'s NPS-hosted points are already LOADED under …",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_BACKCOUNTRY_SHELTERS/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
