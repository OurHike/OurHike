"""Mazamas: challenges, climbing awards earned on the club's own climbs, and not landed (decision 54 wave 5,
section K, 2026-10-04).

/awards/ names three peak awards (Guardian Peaks, Seven Oregon Cascade Peaks, Sixteen Major Northwest Peaks),
'for successfully summiting ... on official Mazama climbs', their peaks named inside a sentence each; the hiking
awards are mileage and leadership tallies. The award winners are Google Sheets, rosters, never read.

The note this replaces read, whole:

Mazamas: challenges, published, and not landed (coverage audit 2026-10-01, batch c6_regional_3).

Each counts only summits made "on official Mazama climbs", so this is a club-member programme for
mountaineering summits. It fits #1780 only loosely.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/awards/` names three peak awards: Guardian Peaks (3 peaks, about
2,000 earned), Seven Oregon Cascade Peaks (7, about 700), and Sixteen Major Northwest Peaks (16, a
plaque, about 500). HTML.

Its `where`: https://mazamas.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://mazamas.org/awards/ (HTTP 200, 129,193 bytes, 2026-10-04): 'A certificate awarded for successfully summiting Mount St. Helens, Mt. Hood, Mt. Adams on official Mazama climbs'",
    ),
    where=("https://mazamas.org/awards/",),
    reason="not this type: awards for the club's own led climbs, their peaks inside sentences",
)
