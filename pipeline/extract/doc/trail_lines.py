"""Dartmouth Outing Club: trail lines, drawn from another folder's resource (coverage audit 2026-10-01,
batch c1_at_clubs_north).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Club polygon "Dartmouth Outing Club". Own geometry: none. "Moosilauke Trail Map" is a printable '
        'download on `/facilities/moosilauke-ravine-lodge/hiking-moosilauke`. ArcGIS "The Dartmouth Fifty 23X" '
        "belongs to the account a personal ArcGIS account, which is excluded under the personal-account rule.",
    ),
    where=("https://dartmouth.edu/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
