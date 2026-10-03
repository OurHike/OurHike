"""Georgia Appalachian Trail Club: places, drawn from another folder's resource (coverage audit
2026-10-01, batch b4_oprhp_mohonk_gatc).

Nothing GATC adds is machine-readable.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/plan-your-hike/trail-communities/` (`modified` 2023-12-20) names the six A.T. Communities: "
        "Blairsville-Union County, Clayton-Rabun County, Dahlonega, Gilmer County, Helen-White County, "
        "Hiawassee-Towns County. They are ATC's designations, already in `communities`.",
    ),
    where=("https://georgia-atclub.org/",),
    reason="drawn from atc/places.py: the six A.T. Communities GATC names are ATC's designations, in `communities`",
)
