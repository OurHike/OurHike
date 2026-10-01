"""NH GRANIT (University of New Hampshire): places, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

NH public and conservation lands are the one GRANIT layer with no obvious better source.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`…/EC/Conservation/MapServer/0` (Conservation Lands): 13,502 polygons. "
        "`…/RecreationResources/MapServer/3` (Recreation Inventory: Areas): 2,718.",
    ),
    where=("https://granit.unh.edu/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
