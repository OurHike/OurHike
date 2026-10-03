"""Carolina Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

Page scrape only. Pages carry leader names, so strip them. The numbered catalogue behind the hike
numbers is not published as a list (UNKNOWN whether one exists publicly). (skeptic) Also
`https://carolinamountainclub.org/lets-go-archive/`: the quarterly Let's Go! hike-schedule PDFs, 102
linked …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://carolinamountainclub.org/find-a-hike/` lists 124 scheduled hikes (2026-10-01). Each detail "
        "page `/find-a-hike/hike/?id=N` gives a catalogue hike number (e.g. 525), distance, loop or one-way, "
        'rating, total elevation gain, description, meeting places and challenge tags (e.g. "Waterfalls '
        '(WC100)"). The data loads via `admin-ajax.php`.',
    ),
    where=(
        "https://carolinamountainclub.org/find-a-hike/",
        "https://carolinamountainclub.org/lets-go-archive/",
        "https://carolinamountainclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
