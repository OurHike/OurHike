"""Susquehanna Appalachian Trail Club: suggested hikes, published as a directory of paragraphs, and not
landed (decision 54 wave 5, section K, 2026-10-04).

satc-hike.org/hiking-in-central-pennsylvania.html lists about 30 places to hike, most of them other
organisations' parks and trails, each a linked name and a paragraph of SATC's prose. Three are SATC's own A.T.
sections, and their distances (6.3, 9.7 and 15.8 miles) sit inside those sentences. Needs a per-site reader that
reads facts out of prose, not built in this pull request.

The note this replaces read, whole:

Susquehanna Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Only the three A.T. entries are the club's own ground.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/hiking-in-central-pennsylvania.html` (page): about 30 entries.
Three describe SATC's own A.T. segments with distances (Clarks Ferry–PA-225 6.3 mi, PA-225–PA-325 9.7
mi, PA-325–PA-443 15.8 mi). The rest are other organisations' parks and trails

Its `where`: https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services https://satc-hike.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.satc-hike.org/hiking-in-central-pennsylvania.html (HTTP 200, 116,903 bytes, 2026-10-04): about 30 entries, each a name (most linking another organisation's site) and a paragraph",
    ),
    where=("https://www.satc-hike.org/hiking-in-central-pennsylvania.html",),
    reason="needs a per-site reader, not built in this pull request: the facts are inside paragraphs of prose",
)
