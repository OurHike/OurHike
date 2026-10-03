"""Alaska Trails: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

The guides belong to whoever wrote them. Load the link, not the text.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Links: 224 of the 286 AKLT segments carry `Trail_Guide_1_Link`, mostly to other publishers' guides "
        "(e.g. `dnr.alaska.gov/parks/brochures/crowpass.pdf`). There are also regional StoryMaps.",
    ),
    where=("https://dnr.alaska.gov/parks/brochures/crowpass.pdf",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
