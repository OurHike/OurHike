"""Mount Rogers Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

Whether those four sections load by script is UNKNOWN (no browser was used).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.mratc.org/suggested-hikes` (page): 7 hikes render (2 A.T., 3 A.T.-linked, 2 Iron "
        "Mountain). Each has distance, one-way or loop, difficulty and turn-by-turn prose, with 15 coordinate "
        "pairs in the text. Four more headings (High Points, Damascus, Grayson Highlands, Backpacking) render "
        "no hikes. 63 scheduled events are in `event-pages-sitemap.xml`.",
    ),
    where=("https://www.mratc.org/suggested-hikes",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
