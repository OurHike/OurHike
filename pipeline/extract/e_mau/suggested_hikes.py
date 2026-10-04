"""E Mau Na Ala Hele: suggested hikes, published as dated events, and not landed (decision 54 wave 5, section
K, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and not a
challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

/upcoming-events.html and /past-events.html announce the group's walks (Lā Hoʻāla Ala Hele, a National Trails
Day walk at Kīholo Bay), each a dated event with meeting directions.

The note this replaces read, whole:

E Mau Na Ala Hele: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Event-shaped. A route has to be inferred

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/upcoming-events.html`, `/past-events.html` (HTML): e.g. the
National Trails Day 2026 Kīholo Bay walk with meeting directions; "walk & talk to Kauleolī and back"; a
~2-mile walk to Koʻa Heiau Holomoana

Its `where`: https://mapservices.nps.gov/arcgis/rest/services https://emaunaalahele.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.emaunaalahele.org/upcoming-events.html (HTTP 200, 32,844 bytes, 2026-10-04T17:39:38Z): 'Upcoming Events', 'Lā Hoʻāla Ala Hele'",
    ),
    where=("https://www.emaunaalahele.org/upcoming-events.html",),
    reason="not this type: dated walks, which the lead ruled are not suggested hikes (2026-10-04)",
)
