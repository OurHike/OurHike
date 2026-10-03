"""Nantahala Hiking Club: trail lines, drawn from another folder's resource (coverage audit 2026-10-01,
batch c3_at_clubs_south).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`centerline` (91 features, 58.9 mi under `NHC`) and `side_trails` (55). The blue-blaze trails in "
        "Nantahala NF arrive via `usfs_trails`. NHC's own geometry: none. `/map-of-the-a-t-at-north-carolina/` "
        "has no content, and `SOBO-by-Sections.pdf` is a schematic.",
    ),
    where=("https://nantahalahikingclub.org/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
