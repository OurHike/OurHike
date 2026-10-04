"""Standing Stone Trail Club: suggested hikes, published as map PDFs only a person can read, and not landed
(decision 54 wave 4, section K, 2026-10-04).

/pdf-maps (updated 2023-04-09) links 13 map PDFs (MAP 1 to MAP 9 and close-ups) under one short description each
('a great day hike'); the one opened (map 1, 9 pages, Esri ArcMap 10.8.1) is a drawing whose text layer is its
labels. The SST Guide is 'available for free upon request' and is not online; /charters are events.

The note this replaces read, whole:

Standing Stone Trail Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Per-map descriptions on `/pdf-maps` (e.g. "Jack's Narrows Close Up
… a great day hike"). `/charters` events (e.g. "Lollipop MeetUp: Top of Jack's Mountain", 10/17). The
SST Guide is "available for free upon request" and is not online.

Its `where`: https://mapservices.pasda.psu.edu/server/rest/services https://standingstonetrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.standingstonetrail.org/pdf-maps (HTTP 200, 790,573 bytes, 2026-10-04T17:39:27Z): 13 PDFs under MAP 1 to MAP 9",
        "30a84d_138e316dab4346cd8bf0e62029e7af21.pdf (HTTP 200, 3,047,839 bytes, Last-Modified 2023-04-09): map labels",
    ),
    where=("https://www.standingstonetrail.org/pdf-maps",),
    reason="a PDF only a person can read: the maps are drawings whose mileages are map labels",
)
