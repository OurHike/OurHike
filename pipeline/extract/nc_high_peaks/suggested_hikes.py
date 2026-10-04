"""NC High Peaks Trail Association: suggested hikes, published as dated group hikes, and not landed (decision 54
wave 4, section K, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and not a
challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

/2026Hikes is the 2026 Hike Schedule, the association's group hikes with their trail, distance and difficulty:
dated outings. The challenge's trail list PDF is the challenges cell's.

The note this replaces read, whole:

NC High Peaks Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Page/PDF.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/2026Hikes`: 17 group hikes with trail, distance and difficulty.
The open-trails table. The challenge's trail list PDF.

Its `where`: https://nchighpeaks.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("https://nchighpeaks.org/2026Hikes (HTTP 200, 25,994 bytes, 2026-10-04T17:39:22Z): '2026 Hike Schedule'",),
    where=("https://nchighpeaks.org/2026Hikes",),
    reason="not this type: dated group hikes, which the lead ruled are not suggested hikes (2026-10-04)",
)
