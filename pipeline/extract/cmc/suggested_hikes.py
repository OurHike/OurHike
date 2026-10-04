"""Carolina Mountain Club: suggested hikes, published as scheduled group hikes, and not landed (decision 54 wave
5, section K, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and not a
challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

/find-a-hike/ lists the club's scheduled hikes (124 on 2026-10-01), each a dated outing with a leader, loaded
through admin-ajax.php; the catalogue numbers behind them (a hike's number, e.g. 525) are not published as a list.
carolinamountainclub.org's robots.txt asks `Crawl-delay: 10`.

The note this replaces read, whole:

Carolina Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

Page scrape only. Pages carry leader names, so strip them. The numbered catalogue behind the hike
numbers is not published as a list (UNKNOWN whether one exists publicly). (skeptic) Also
`https://carolinamountainclub.org/lets-go-archive/`: the quarterly Let's Go! hike-schedule PDFs, 102
linked …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `https://carolinamountainclub.org/find-a-hike/` lists 124
scheduled hikes (2026-10-01). Each detail page `/find-a-hike/hike/?id=N` gives a catalogue hike number
(e.g. 525), distance, loop or one-way, rating, total elevation gain, description, meeting places and
challenge tags (e.g. "Waterfalls (WC100)"). The data loads via `admin-ajax.php`.

Its `where`: https://carolinamountainclub.org/find-a-hike/
https://carolinamountainclub.org/lets-go-archive/ https://carolinamountainclub.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://carolinamountainclub.org/find-a-hike/ (HTTP 200, 325,053 bytes, 2026-10-04T17:39:53Z): scheduled hikes, 'Shining Rock from Black Balsam #1' and the rest",
    ),
    where=("https://carolinamountainclub.org/find-a-hike/",),
    reason="not this type: dated group hikes, which the lead ruled are not suggested hikes (2026-10-04)",
)
