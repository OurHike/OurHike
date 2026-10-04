"""Alaska Trails: suggested hikes, linked to other publishers' guides, and not landed (decision 54 wave 4,
section K, 2026-10-04).

224 of AKLT's 286 segments carry a Trail_Guide_1_Link (the coverage audit), most to another publisher's brochure
(Alaska State Parks' crowpass.pdf among them): the links are an ArcGIS layer's field, the lead's cell, and the
guides are other agencies' to publish. No request sent today.

The note this replaces read, whole:

Alaska Trails: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

The guides belong to whoever wrote them. Load the link, not the text.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Links: 224 of the 286 AKLT segments carry `Trail_Guide_1_Link`,
mostly to other publishers' guides (e.g. `dnr.alaska.gov/parks/brochures/crowpass.pdf`). There are also
regional StoryMaps.

Its `where`: https://dnr.alaska.gov/parks/brochures/crowpass.pdf

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) 224 of the 286 AKLT segments carry Trail_Guide_1_Link, mostly to other publishers' guides; regional StoryMaps",
    ),
    where=("https://dnr.alaska.gov/parks/brochures/crowpass.pdf",),
    reason="not this club's: the guides are other publishers', linked from an ArcGIS layer's field",
)
