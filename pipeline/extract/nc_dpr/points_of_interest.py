"""NC Division of Parks & Recreation — NC Trails: points of interest, published, and not landed
(coverage audit 2026-10-01, batch c9_federal_state_rest).

No campsite, shelter or water layer found in DPR's 88-service org. PDF is the weakest form. Skeptic
re-checked with an ArcGIS search of org `nRIB86xC7kq6wavB` (92 feature services, most of them other
DNCR divisions). It found no facility layer either, only `NC_State_Parks_Points_STANDARD` ("NCSP …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NC_State_Parks_Points/FeatureServer/0`: 48 park points (office addresses). Facilities appear only on "
        "park map PDFs, e.g. `ncparks.gov/maps/mount-mitchell-state-park-area-trails-map/open`.",
    ),
    where=(
        "https://services6.arcgis.com/nRIB86xC7kq6wavB/arcgis/rest/services/NC_State_Parks_Points/FeatureServer/0",
        "https://ncparks.gov/maps/mount-mitchell-state-park-area-trails-map/open",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
