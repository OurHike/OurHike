"""Tidewater Appalachian Trail Club: points of interest, drawn from another folder's resource (coverage
audit 2026-10-01, batch c2_at_clubs_mid).

The cabin is not a hiker POI, because only members can reserve it (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'via atc `shelters` (Harpers Creek capacity 6, Maupin Field capacity 6) and `parking` ("Tye River (VA '
        'Rte 56) Parking Area"). Club: Douglas Putman Memorial Cabin (`/cabin/` + PDFs): members-only, about 4 '
        'mi off the A.T., no coordinates. "A.T. Maintenance Access Points" PDF (2022-05-15): driving directions'
        " for maintainers",
    ),
    where=("https://tidewateratc.org/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
