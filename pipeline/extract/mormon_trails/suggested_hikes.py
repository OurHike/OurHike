"""Mormon Trails Association: suggested hikes, none: its tours are driving, cemetery and guided walking tours
(decision 54 wave 5, section K, 2026-10-04).

/tours/ lists the Emigration Tour, the Cemeteries Tour, the Holladay Tour and the SLC Walking Tour, a paid tour
booked with a guide; the auto tour is a drive. None is a hike with facts a hiker follows on their own.

The note this replaces read, whole:

National Mormon Trails Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Urban and paid walks

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Own: `/tours/` (Holladay Walking Tour, the Emigration Tour
"Crossing the Wasatch Mountains", cemetery tours), `/slc-walking-tour/` (a paid, booked guided tour),
`/auto-tour/`

Its `where`: https://mormontrails.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://mormontrails.org/tours/ (HTTP 200, 175,899 bytes, 2026-10-04T17:39:43Z): Emigration, Cemeteries, Holladay and SLC Walking tours",
    ),
    where=("https://mormontrails.org/tours/",),
    reason="not this type: history tours by car and with a guide, not hikes",
)
