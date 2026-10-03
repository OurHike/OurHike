"""The Trustees of Reservations: challenges, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

This is the place-based shape #1780 — Let a club publish a challenge — places on its own trails that
hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List models, but it was
an April 2022 school-vacation programme. Pages that are still live do not make it a running …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The "Hike Trustees" challenge was sunsetted 2024-01-01, per `/content/hike-trustees-pause-faqs/` '
        '(found by web search). Separately, "Trustees Quest": `/content/trustees-quest-clue-sheets/` (modified '
        "2022-04-15) lists 5 Quest locations (Bartholomew's Cobble, Copicut Woods, Long Hill, Rock House "
        "Reservation, Rocky Woods). Each has a `/content/trustees-quest-badge-<place>/` page that awards a "
        'digital badge at a named spot, e.g. Rocky Woods: "You are on the summit of Cedar Hill… 435 feet above '
        'sea level" (modified 2022-04-13).',
    ),
    where=("https://thetrustees.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
