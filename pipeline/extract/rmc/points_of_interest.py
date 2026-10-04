"""Randolph Mountain Club: points of interest, published with no coordinate, and not landed (decision 54, wave 5,
read live 2026-10-04).

The RMC's four camps (Gray Knob, Crag Camp, The Log Cabin, The Perch) each have a page with the camp's
capacity, height, caretaker and water ("Water is available from a spring, approximately a quarter mile east on
the Gray Knob Trail", Gray Knob's), and none states a coordinate. A point is never looked up from a name, so
nothing places them here. ATC's layers hold only The Perch (atc, code 2, the coverage audit 2026-10-01); Gray
Knob, Crag Camp and the Log Cabin are not in them, so a hiker on the Northern Presidentials does not see three
year-round shelters. Needs a per-site reader, not built in this pull request: the facts on each page, joined to
a fix a person reviews.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (Yoast's, `Disallow:` empty, no Crawl-delay), then /camps/ and /camps/gray-knob/, read "
        "2026-10-04 under lib/user_agent.py's agent: four camps, Gray Knob 'a capacity of 15 persons', 'nestled at "
        "4,372 feet', 'a caretaker is in residence year-round', water from a spring a quarter mile east; no "
        "coordinate, decimal or DDM, anywhere in either page.",
        "/trails/interactive-trail-map/ (read 2026-10-04): the map is 'a window of a larger online map database "
        "maintained by Trailforks', a third party's, with no KML, GeoJSON or ArcGIS layer of the RMC's own.",
        "the coverage audit (2026-10-01, batch c1_at_clubs_north): ATC code 2 holds only The Perch; Crag Camp's 20 "
        "and the Log Cabin's 10 are SOURCE_SURVEY.md's search results, never read off the pages.",
    ),
    where=(
        "https://randolphmountainclub.org/camps/",
        "https://randolphmountainclub.org/camps/gray-knob/",
        "https://randolphmountainclub.org/trails/interactive-trail-map/",
    ),
    reason="needs a per-site reader, not built in this pull request: the camps' pages give capacity and water and no coordinate",
)
