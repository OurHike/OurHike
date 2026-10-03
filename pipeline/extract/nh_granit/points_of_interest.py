"""NH GRANIT (University of New Hampshire): points of interest, published, and not landed (coverage
audit 2026-10-01, batch c9_federal_state_rest).

Same compiled-inventory provenance as the retired trails. AMC huts and WMNF shelters are better
sourced from AMC and USFS.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`…/RecreationResources/MapServer/1` (Recreation Inventory: Points): 1,541. Trailhead 719, Parking 651,"
        " Gate 57, Shelter 48, Wildlife Viewing 30, Hut/Lodge/Cabin 21, Park Office 11, Lookout Tower 4. Layer "
        "0 (access sites to public waters): 990.",
    ),
    where=("https://granit.unh.edu/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
