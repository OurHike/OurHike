"""Piedmont Appalachian Trail Hikers: photos, drawn from another folder's resource (coverage audit
2026-10-01, batch c3_at_clubs_south).

The Burgess Scans are photos of people, not of features, and are not openly licensed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`Photo1` is populated on 5 of 5 shelters. "The Burgess Scans" '
        "(`miscellany.neuseriversailors.com/Burgess_Scans/`) holds 1984–2000s club-activity photos under "
        '"Copyright © 2018-2025 Paul M. Clayton".',
    ),
    where=("https://miscellany.neuseriversailors.com/Burgess_Scans/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
