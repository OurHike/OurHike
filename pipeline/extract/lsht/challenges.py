"""Lone Star Hiking Trail Club: challenges, refused by the host (decision 54 wave 5, section K, 2026-10-04).

lonestartrail.org answered HTTP 403 to our named agent on 2026-10-04 (lsht/suggested_hikes.py). Its Honor Roll is a
roster of those who finished in any case.

The note this replaces read, whole:

Lone Star Hiking Trail Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

The programme only. The list holds names and emails "if permitted".

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Honor Roll": "Congratulations on completing your journey of the
entire Lone Star Hiking Trail! Join our Honor Roll…", with a form at
`content.aspx?page_id=1478&club_id=738078&item_id=10519`.

Its `where`: https://apps.fs.usda.gov/arcx/rest/services https://lonestartrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("https://lonestartrail.org/: HTTP 403 (118 bytes) to our agent, 2026-10-04T17:46:01Z",),
    where=("https://lonestartrail.org/",),
    reason="refused: the host answers HTTP 403 to our named agent",
)
