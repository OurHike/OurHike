"""The Trustees of Reservations: challenges, the Hike Trustees challenge ended, and not landed (decision 54
wave 5, section K, 2026-10-04).

The 'Hike Trustees' challenge was sunsetted on 2024-01-01 (/content/hike-trustees-pause-faqs/, the coverage audit);
the Trustees Quest's clue sheets (/content/trustees-quest-clue-sheets/, five locations) were last modified
2022-04-15 and nothing says the Quest still runs. No request sent today.

The note this replaces read, whole:

The Trustees of Reservations: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

This is the place-based shape #1780 — Let a club publish a challenge — places on its own trails that
hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List models, but it was an
April 2022 school-vacation programme. Pages that are still live do not make it a running …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The "Hike Trustees" challenge was sunsetted 2024-01-01, per
`/content/hike-trustees-pause-faqs/` (found by web search). Separately, "Trustees Quest":
`/content/trustees-quest-clue-sheets/` (modified 2022-04-15) lists 5 Quest locations (Bartholomew's
Cobble, Copicut Woods, Long Hill, Rock House Reservation, Rocky Woods). Each has a
`/content/trustees-quest-badge-<place>/` page that awards a digital badge at a named spot, e.g. Rocky
Woods: "You are on the summit of Cedar Hill… 435 feet above sea level" (modified 2022-04-13).

Its `where`: https://thetrustees.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /content/hike-trustees-pause-faqs/ and /content/trustees-quest-clue-sheets/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://thetrustees.org/content/hike-trustees-pause-faqs/",),
    reason="not current: the Hike Trustees challenge ended on 2024-01-01, and the Quest's sheets date from 2022",
)
