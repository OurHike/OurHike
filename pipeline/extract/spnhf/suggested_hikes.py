"""Society for the Protection of New Hampshire Forests: suggested hikes, inside its 184 property pages' prose,
and not landed (decision 54 wave 5, section K, 2026-10-04).

The property pages describe their hikes in sentences (Mount Major: 'round trip hike ranging from 3 to 3.9 miles',
the coverage audit); no page states a hike's facts as a fact. No request sent today.

The note this replaces read, whole:

Society for the Protection of NH Forests: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

A page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Property pages carry hike descriptions (Mount Major: "round trip
hike ranging from 3 to 3.9 miles"), across 184 pages.

Its `where`: https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services
https://forestsociety.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("(the coverage audit, 2026-10-01) 184 property pages, hike descriptions in prose",),
    where=("https://forestsociety.org/",),
    reason="needs a per-site reader, not built in this pull request: the facts are inside paragraphs of prose",
)
