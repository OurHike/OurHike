"""Georgia Appalachian Trail Club: photos, drawn from another folder's resource (coverage audit
2026-10-01, batch b4_oprhp_mohonk_gatc).

The loaded photos rest on ATC's permission, not on anything GATC granted.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "ATC `Photo1` is populated on GATC rows: campsites 26, parking 19, shelters 14, viewpoints 0. GATC's "
        'own site: "© 2026. All Rights Reserved.", 1,100 WP media items.',
    ),
    where=("https://georgia-atclub.org/",),
    reason="drawn from atc/points_of_interest.py: ATC's `Photo1` on GATC's campsites, parking and shelters, which rest"
    " on ATC's permission rather than anything GATC granted",
)
