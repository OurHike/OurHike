"""Cumberland Valley Appalachian Trail Club: trail lines, drawn from another folder's resource
(coverage audit 2026-10-01, batch c2_at_clubs_mid).

PATC's trails layer names "CVATC" as `Maintainer` on 20 segments (Measured), so CVATC's ground also
turns up in PATC's data.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "via atc `centerline`. Own: `/appalachian-trail-section-map.html` is a JPEG "
        "(`/uploads/5/5/1/9/55196425/cvatmap-1200_orig.jpg`), not geometry",
    ),
    where=("https://cvatclub.org/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
