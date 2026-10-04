"""Sheltowee Trace Association: suggested hikes, published as dated organized hikes, and not landed (decision 54
wave 4, section K, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and not a
challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

/organizedhikes announces the association's upcoming organized hike ('Upcoming Hike: Van Hook Falls', 2026-10-11,
'5.7 miles ... 626ft of gain'), with member registration: dated outings. The Hiker Challenge schedule PDF is the
challenges cell's. The page's 2023_resupply_and_trail_angels.pdf names people who help hikers and is never read;
major_trailheads.pdf is points of interest.

The note this replaces read, whole:

Sheltowee Trace Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/organizedhikes` (members only, e.g. "Van Hook Falls",
2026-10-11, "5.7 miles … 626ft of gain"). The Hiker Challenge schedule PDF,
`/s/2026NorthtoSouthHikerChallengeSchedule_updated_Sept30_2026.pdf`.

Its `where`: https://sheltoweetrace.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://sheltoweetrace.org/organizedhikes (HTTP 200, 378,827 bytes, 2026-10-04T17:39:29Z): 'Upcoming Hike: Van Hook Falls'",
    ),
    where=("https://sheltoweetrace.org/organizedhikes",),
    reason="not this type: dated group hikes, which the lead ruled are not suggested hikes (2026-10-04)",
)
