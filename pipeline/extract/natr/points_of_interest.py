"""Natchez Trace NST (NPS-administered): points of interest, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

The `nps-poi` row is on hold for scope (c9). These counts are NATR's share of it. Skeptic
spot-check: `UNITCODE='NATR'` = 854; `UNITCODE='POHE'` = 0.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`nps-poi` layer `NPS_Public_POIs_Geographic/MapServer/0`, `UNITCODE='NATR'`: 854: Mile Marker 372, "
        "Parking Lot 140, Trailhead 78, Picnic Area 43, Restroom 25, Overlook 19, Campground 7, Ranger Station "
        "7, Visitor Center 7, Spring 5. API `/campgrounds`: 3 (Rocky Springs MP 54.8, Jeff Busby MP 193.1, "
        "Meriwether Lewis MP 385.9).",
    ),
    where=("https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs_Geographic/MapServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
