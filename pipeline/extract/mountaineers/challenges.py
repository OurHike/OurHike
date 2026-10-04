"""The Mountaineers: challenges, refused by the host (decision 54 wave 5, section K, 2026-10-04).

mountaineers.org answers HTTP 403 to our named agent (mountaineers/suggested_hikes.py), so the award badges and
peak pins ('Seattle Branch Snoqualmie First Ten') are not read.

The note this replaces read, whole:

The Mountaineers: challenges, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Award badges and peak pins at `/membership/badges/award-badges`,
e.g. "Seattle Branch Snoqualmie First Ten" and "Second Ten" with their peak lists.

Its `where`: https://mountaineers.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("https://www.mountaineers.org/: HTTP 403 to our agent, 2026-10-04 (mountaineers/suggested_hikes.py)",),
    where=("https://www.mountaineers.org/membership/badges/award-badges",),
    reason="refused: the host answers HTTP 403 to our named agent",
)
