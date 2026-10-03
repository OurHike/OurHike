"""Randolph Mountain Club: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c1_at_clubs_north).

Gray Knob, Crag Camp and the Log Cabin are not in ATC's shelters layer (a name query returned only
The Perch). Capacities of Crag Camp (20) and the Log Cabin (10) are SOURCE_SURVEY.md's search
results, never read off the pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "ATC (code 2) has only The Perch: shelter 1, campsite 1, privy 1, viewpoints 2. "
        "`https://randolphmountainclub.org/camps/` (page) lists four camps. Gray Knob: capacity 15, 4,372 ft, "
        "caretaker year-round, fee table (`/camps/gray-knob/`). Crag Camp and The Log Cabin have their own "
        'pages. "All sites have a water source nearby, and a single outhouse".',
    ),
    where=(
        "https://randolphmountainclub.org/camps/",
        "https://randolphmountainclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
