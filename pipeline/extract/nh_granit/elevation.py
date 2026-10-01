"""NH GRANIT (University of New Hampshire): elevation, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Very likely the same lidar projects 3DEP serves (Reasoned). No reason to add it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`…/Topical/CV_LiDAR_DigitalElevation/MapServer` (Digital Elevation); image tile index "
        "`Topical/WF_NHGeodataImageDownloadTileIndex`.",
    ),
    where=("https://granit.unh.edu/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
