"""Adirondack Mountain Club: challenges, refused by ADK's terms (decision 54 wave 5, section K, 2026-10-04).

The ADK Fire Tower Challenge (23 summits) is on adk.org, whose terms forbid access by automated means, as
adk/suggested_hikes.py quotes them; nothing is read.

The note this replaces read, whole:

Adirondack Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page. The 46ers are a separate org.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/adk-fire-tower-challenge/`: 23 summits (18 of 27 Adirondack plus
all 5 Catskill), a patch, proof of stewardship.

Its `where`: https://adk.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "adk/suggested_hikes.py's note quotes adk.org's terms, read 2026-10-04",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://adk.org/adk-fire-tower-challenge/",),
    reason="refused: ADK's terms forbid access by automated means (adk/suggested_hikes.py quotes them)",
)
